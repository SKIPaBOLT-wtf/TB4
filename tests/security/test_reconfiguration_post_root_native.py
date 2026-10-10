"""Actual protected post-root frames/cuts; synthetic SDK authority only."""
from contextlib import contextmanager
from dataclasses import replace
import pytest

from tb4.commissioning_checks import detect_environment
from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import native_settings,SettingsError
from tb4.reconfiguration_post_root import PostRootCandidate
from reconfiguration_post_root_support import candidate_for,checker_for
from test_reconfiguration_rebind_native import native_system as rebind_native_system
from test_private_settings_native import fixture,protect_fixture


def native_system(root,store):
    def private(name):return native_settings(root.parent/name,create=True,owner_authorized=True)
    s=rebind_native_system(root,private("post-rebind"))
    assert s.rebind.begin(owner_authorized=True)=="PREPARED"
    assert s.rebind.advance(owner_authorized=True)=="REBOUND"
    context,candidate=candidate_for(s.rebind,profile=store,archive=private("post-archive"),transaction=private("post-transaction"))
    checker=checker_for(s.rebind,environment=lambda:detect_environment(launch_mode="EXTERNAL"))
    return s,context,candidate,checker


@pytest.mark.parametrize("which",["transaction","archive","profile"])
def test_actual_native_post_root_promotion_cut_recovers_exact_frame_without_remote_repeat(fixture,which):
    root,store=fixture;s,context,candidate,checker=native_system(root,store)
    original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    selected=getattr(context,which);locked=selected.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            port.promote=lambda:(_ for _ in ()).throw(OSError("SYNTHETIC_POST_ROOT_PROMOTION_CUT"))
            yield port
    selected.native.locked=cut
    with pytest.raises((SettingsError,ConfigurationError)):candidate.begin(owner_authorized=True)
    selected.native.locked=locked
    with locked() as port:pending=port.read("settings.pending")
    assert pending is not None
    assert candidate.recover_local(which,owner_authorized=True)=="INSPECT_REQUIRED"
    with locked() as port:assert port.read("settings.json")==pending
    assert PostRootCandidate(context).resume_staging(owner_authorized=True)["phase"]=="STAGED"
    assert PostRootCandidate(context).require_validated(checker).revision==store.read().revision
    assert s.value.setup.store.read()==original and len(s.value.provider.store.calls)==writes and len(s.moves)==3


def test_actual_native_post_root_copy_and_broad_protection_are_refused(fixture):
    root,store=fixture;s,context,candidate,checker=native_system(root,store)
    original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    candidate.begin(owner_authorized=True);candidate.require_validated(checker)
    foreign=root.parent/"foreign-post-root";copied=native_settings(foreign,create=True,owner_authorized=True)
    target=foreign/"settings.json";target.write_bytes((root/"settings.json").read_bytes());protect_fixture(target)
    with pytest.raises((SettingsError,ConfigurationError)):
        PostRootCandidate(replace(context,profile=copied)).require_validated(checker)
    protect_fixture(root,broad=True)
    try:
        with pytest.raises((SettingsError,ConfigurationError)):candidate.require_validated(checker)
    finally:protect_fixture(root)
    assert s.value.setup.store.read()==original and len(s.value.provider.store.calls)==writes
