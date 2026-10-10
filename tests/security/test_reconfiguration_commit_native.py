"""Actual native C4 pending/copy/budget boundaries; synthetic SDK only."""
from contextlib import contextmanager
from dataclasses import replace
import copy
import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.drive.commissioning import frozen_plan
from tb4.drive.docs_authority import AuthorityError
from tb4.private_settings import native_settings,SettingsError
from tb4.reconfiguration_commit import CommitContext,ConfigurationCommit
from test_reconfiguration_post_root_native import native_system as post_native_system
from test_reconfiguration_commit import large_commit_plan
from test_private_settings_native import fixture,protect_fixture


def native_system(root,store):
    profile=native_settings(root.parent/"commit-post-profile",create=True,owner_authorized=True)
    s,post_context,candidate,checker=post_native_system(root,profile)
    candidate.begin(owner_authorized=True)
    context=CommitContext(candidate,store)
    return s,context,ConfigurationCommit(context),checker


@pytest.mark.parametrize("at",["begin","invoking","confirmed"])
def test_actual_native_commit_pending_cut_promotes_exact_frame_and_never_repeats(fixture,at):
    root,store=fixture;s,context,commit,checker=native_system(root,store);locked=store.native.locked
    if at!="begin":commit.begin(checker,owner_authorized=True,decided_at=220)
    original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    @contextmanager
    def cut():
        with locked() as port:
            promote=port.promote
            def stop():
                value=store._decode(port.read("settings.pending"),port.binding).payload
                if value["dispatch"]=={"begin":"PREPARED","invoking":"INVOKING","confirmed":"CONFIRMED"}[at]:
                    raise OSError("SYNTHETIC_COMMIT_PROMOTION_CUT")
                return promote()
            port.promote=stop;yield port
    store.native.locked=cut
    with pytest.raises((SettingsError,ConfigurationError)):
        commit.begin(checker,owner_authorized=True,decided_at=220) if at=="begin" else commit.advance(checker,owner_authorized=True)
    store.native.locked=locked;pending=(root/"settings.pending").read_bytes()
    with pytest.raises(SettingsError):store.read()
    assert commit.recover_local(owner_authorized=True)=="INSPECT_REQUIRED"
    assert (root/"settings.json").read_bytes()==pending
    fresh=ConfigurationCommit(context)
    assert fresh.inspect()=={"begin":"PREPARED","invoking":"UNKNOWN","confirmed":"PUBLISHED"}[at]
    assert len(s.value.provider.store.calls)==writes+(1 if at=="confirmed" else 0)
    assert s.value.setup.store.read()==original and len(s.moves)==3


def test_actual_native_commit_copy_and_broad_protection_are_refused(fixture):
    root,store=fixture;s,context,commit,checker=native_system(root,store)
    commit.begin(checker,owner_authorized=True,decided_at=220);original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    foreign=root.parent/"foreign-configuration-commit";copied=native_settings(foreign,create=True,owner_authorized=True)
    target=foreign/"settings.json";target.write_bytes((root/"settings.json").read_bytes());protect_fixture(target)
    with pytest.raises((SettingsError,ConfigurationError)):
        ConfigurationCommit(replace(context,store=copied)).advance(checker,owner_authorized=True)
    protect_fixture(root,broad=True)
    try:
        with pytest.raises((SettingsError,ConfigurationError)):commit.advance(checker,owner_authorized=True)
    finally:protect_fixture(root)
    assert len(s.value.provider.store.calls)==writes and s.value.setup.store.read()==original


def test_actual_native_commit_compact64_plan_and_previous_frame_stay_within_budget(fixture):
    root,store=fixture;s,context,commit,checker=native_system(root,store)
    commit.begin(checker,owner_authorized=True,decided_at=220);current=store.read()
    plan,_=large_commit_plan(current.payload["pin"]);frame=copy.deepcopy(current.payload)
    frame.update(transition_id=plan._validate()[1]["configuration"]["transition_id"],plan=frozen_plan(plan))
    # Native frame budget only: no claim of runtime/profile admission.
    store.save(frame,expected_revision=current.revision);invoking={**frame,"dispatch":"INVOKING"}
    store.save(invoking,expected_revision=current.revision+1)
    assert store.read().payload==invoking and store.read().previous==frame
    assert (root/"settings.json").stat().st_size<=1024*1024 and not (root/"settings.pending").exists()
    writes=len(s.value.provider.store.calls)
    with pytest.raises((SettingsError,ConfigurationError,ValueError,AuthorityError)):
        commit.advance(checker,owner_authorized=True)
    assert len(s.value.provider.store.calls)==writes
