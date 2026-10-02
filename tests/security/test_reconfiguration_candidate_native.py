"""Real protected staged profile frames, restart, copy and interruption checks."""
from contextlib import contextmanager
import pytest

from tb4.commissioning_checks import detect_environment
from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import native_settings, SettingsError
from tb4.reconfiguration_candidate import Candidate, CandidateContext
from reconfiguration_candidate_support import system
from test_private_settings_native import fixture, protect_fixture


def native_system(root,store):
    def private(name):
        return native_settings(root.parent/name,create=True,owner_authorized=True)
    return system(profile=store,archive=private("candidate-archive"),transaction=private("candidate-transaction"),
        profile_store=private("original"),checkpoint_store=private("checkpoint"),
        effect_store=private("effects"),state_store=private("maintenance"),baseline_store=private("baseline"),
        environment=lambda:detect_environment(launch_mode="DESKTOP_SESSION"))


def test_actual_native_candidate_retains_original_frames_and_requires_restart_review(fixture,capsys):
    root,store = fixture; s = native_system(root,store)
    original_root = root.parent/"original"
    raw = (original_root/"settings.json").read_bytes()
    assert s.candidate.begin(owner_authorized=True)["phase"] == "STAGED"
    assert s.candidate.review(s.checker)["settings_validated"]
    reopened = Candidate(s.context)
    assert not reopened.view()["settings_validated"]
    assert reopened.require_validated(s.checker).revision == store.read().revision
    assert (original_root/"settings.json").read_bytes() == raw
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("which",["transaction","archive","profile"])
def test_actual_native_cut_recovery_preserves_exact_candidate_and_never_sends(fixture,which):
    root,store = fixture; s = native_system(root,store)
    selected = getattr(s.context,which); locked = selected.native.locked
    original = (root.parent/"original"/"settings.json").read_bytes()
    commits = s.value.provider.store.commits
    @contextmanager
    def cut():
        with locked() as port:
            port.promote = lambda: (_ for _ in ()).throw(OSError("SYNTHETIC_CANDIDATE_CUT"))
            yield port
    selected.native.locked = cut
    with pytest.raises(SettingsError,match="COMMIT_UNCONFIRMED"):
        s.candidate.begin(owner_authorized=True)
    selected.native.locked = locked
    with locked() as port:
        pending = port.read("settings.pending")
    assert s.candidate.recover_local(which,owner_authorized=True) == "INSPECT_REQUIRED"
    with locked() as port:
        assert port.read("settings.json") == pending
    assert Candidate(s.context).resume_staging(owner_authorized=True)["phase"] == "STAGED"
    assert (root.parent/"original"/"settings.json").read_bytes() == original
    assert s.value.provider.store.commits == commits


def test_copied_native_staged_profile_cannot_replace_original_or_qualify(fixture):
    root,store = fixture; s = native_system(root,store); s.candidate.begin(owner_authorized=True)
    original = (root.parent/"original"/"settings.json").read_bytes()
    foreign = root.parent/"foreign-candidate"
    copied = native_settings(foreign,create=True,owner_authorized=True)
    target = foreign/"settings.json"; target.write_bytes((root/"settings.json").read_bytes()); protect_fixture(target)
    context = CandidateContext(s.value.controller,s.context.resolution,copied,s.context.archive,s.context.transaction)
    with pytest.raises((ConfigurationError,SettingsError)):
        Candidate(context).require_validated(s.checker)
    assert (root.parent/"original"/"settings.json").read_bytes() == original


def test_broad_native_candidate_protection_refuses_review_without_provider_write(fixture):
    root,store = fixture; s = native_system(root,store); s.candidate.begin(owner_authorized=True)
    original = (root.parent/"original"/"settings.json").read_bytes()
    commits = s.value.provider.store.commits
    protect_fixture(root,broad=True)
    try:
        with pytest.raises((ConfigurationError,SettingsError)):
            s.candidate.require_validated(s.checker)
    finally:
        protect_fixture(root)
    assert (root.parent/"original"/"settings.json").read_bytes() == original
    assert s.value.provider.store.commits == commits
