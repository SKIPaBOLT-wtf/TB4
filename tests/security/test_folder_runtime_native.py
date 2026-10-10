"""Actual native normal commissioning with explicitly synthetic wire replies."""
from dataclasses import replace

import pytest

from tb4.commissioning_checks import detect_environment
from tb4.commissioning_state import Setup, DenyActivation, Validation
from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError, WriteResult
from tb4.drive.folder_first_run import RemoteFolderCommissioning
from tb4.drive.folder_prerequisites import native_folder_prerequisites
from tb4.drive.folder_runtime import NativeFolderCommissioning
from tb4.drive.leadership import Leadership
from tb4.private_settings import native_settings, SettingsError
from tb4.reconfiguration_admission import AdmissionContext, ConfigurationAdmission
from tb4.watchdog.checkpoint_store import NativeCheckpoint
from tests.security.test_first_run import FACTS
from tests.security.test_folder_connection_native import commit, saved
from tests.security.test_folder_prerequisites_native import system as first_run
from tests.security.test_folder_authority_transport_native import desired
from tests.security.test_private_settings_native import fixture, protect_fixture, SUPPORTED

pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Actual native normal Folder commissioning")


def system(fixture, monkeypatch):
    v = first_run(fixture, monkeypatch)
    v.checker = native_folder_prerequisites(v.settings, access=v.access,
        environment=lambda:detect_environment(launch_mode="EXTERNAL"),
        source=v.source, runtime=FACTS, clock=lambda:v.now[0], normal_authority=True)
    v.port = v.checker.storage.port
    return v


def test_actual_native_opt_in_constructor_has_no_key_proof_write_or_default_change(fixture, monkeypatch):
    v = first_run(fixture, monkeypatch)
    assert type(v.checker.storage.port) is RemoteFolderCommissioning
    before, calls = saved(v), len(v.calls)
    def forbidden(*_args, **_kwargs): pytest.fail("Constructor used a key or rewrote native settings")
    monkeypatch.setattr(v.store._native.__class__, "open_key", forbidden)
    monkeypatch.setattr(v.settings.__class__, "_save_locked", forbidden)
    checker = native_folder_prerequisites(v.settings, access=v.access,
        environment=lambda:detect_environment(launch_mode="EXTERNAL"),
        source=v.source, runtime=FACTS, clock=lambda:v.now[0], normal_authority=True)
    assert type(checker.storage.port) is NativeFolderCommissioning
    checker.storage.port.authority(v.authority)
    assert len(v.calls) == calls and saved(v) == before


def test_actual_native_opt_in_proof_read_cas_readback_keeps_profile_and_default_denial(fixture, monkeypatch, capsys):
    v = system(fixture, monkeypatch)
    before = saved(v)
    assert type(v.checker.validate(v.settings.read().payload)) is Validation
    client = v.port.authority(v.authority)
    observed = client.read(); value = desired(observed)
    assert client.compare_replace(observed, value) is WriteResult.ACCEPTED
    assert client.read().document() == value
    assert saved(v) == before
    setup = Setup(v.settings)
    assert setup.review(v.checker)["settings_validated"]
    assert setup.activate(v.checker, DenyActivation())["reason"] == "ACTIVATION_NOT_AUTHORIZED"
    assert setup.store.read().payload["credential_image"] == before[0].payload["credential_image"]
    assert v.metadata.read() == before[1] and v.key.read_bytes() == before[2]
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("change", ["unselected", "revoked", "selection-revoked", "key-version",
    "known-version", "key-permission", "known-permission", "expired"])
def test_actual_native_normal_port_rechecks_current_loss_before_transport(fixture, monkeypatch, change):
    v = system(fixture, monkeypatch)
    client = v.port.authority(v.authority); client.read()
    if change == "unselected": commit(v, lambda p:p["choices"].update(credentials=[]))
    if change == "revoked": commit(v, lambda p:p["credential_image"]["bindings"][v.handle].update(revoked=True))
    if change == "selection-revoked":
        commit(v, lambda p:[r.update(revoked=True) for r in p["credential_image"]["selections"].values()])
    if change == "key-version": v.key.write_bytes(b"synthetic-replaced-runtime-key")
    if change == "known-version": v.known.write_bytes(b"synthetic-replaced-runtime-known")
    if change == "key-permission": protect_fixture(v.key, broad=True)
    if change == "known-permission": protect_fixture(v.known, broad=True)
    if change == "expired": v.now[0] = 201
    calls, profile = len(v.calls), v.settings.read()
    with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): client.read()
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"): v.checker.validate(profile.payload)
    assert len(v.calls) == calls and v.settings.read() == profile and v.checker.credentials is None


@pytest.mark.parametrize("fault", ["duck", "root", "seal", "tab"])
def test_actual_normal_authority_bad_handle_refuses_before_native_io(fixture, monkeypatch, fault):
    v = system(fixture, monkeypatch)
    handle = v.authority
    if fault == "duck": handle = object()
    if fault == "root": handle = replace(handle, object_id=v.spec.domain_id)
    if fault == "seal": handle = replace(handle, seal="c"*64)
    if fault == "tab": handle = replace(handle, tab_id="synthetic-tab")
    def forbidden(*_args, **_kwargs): pytest.fail("Invalid authority handle reached native IO")
    monkeypatch.setattr(v.settings.native, "locked", forbidden)
    with pytest.raises(AuthorityError, match="^FOLDER_RUNTIME_AUTHORITY$"): v.port.authority(handle)


@pytest.mark.parametrize("field", ["_connection", "_access", "_proof", "spec", "mode"])
def test_actual_mutated_normal_composition_never_uses_cached_authority(fixture, monkeypatch, field):
    v = system(fixture, monkeypatch)
    calls = len(v.calls)
    setattr(v.port, field, object())
    with pytest.raises(AuthorityError, match="^FOLDER_RUNTIME_CHANGED$"): v.port.authority(v.authority)
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"): v.checker.validate(v.settings.read().payload)
    assert len(v.calls) == calls


@pytest.mark.parametrize("flag", [None, 1, "enabled"])
def test_untyped_normal_opt_in_refuses_before_profile_lookup(fixture, monkeypatch, flag):
    root, profile = fixture
    def forbidden(*_args, **_kwargs): pytest.fail("Untyped flag looked up a profile")
    monkeypatch.setattr(profile, "read", forbidden)
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"):
        native_folder_prerequisites(profile, access=None, environment=None, source=None,
            runtime=None, clock=None, normal_authority=flag)


def test_hidden_image_authority_scope_and_local_unknown_have_separate_meanings(fixture, monkeypatch):
    v = system(fixture, monkeypatch)
    commit(v, lambda p:p["operations"].update({"e"*64:"UNKNOWN"}))
    client = v.port.authority(v.authority)
    client.read()
    profile = v.settings.read()
    assert Setup(v.settings).review(v.checker)["reason"] == "UNKNOWN_OPERATION"
    assert v.settings.read().payload["operations"] == profile.payload["operations"]
    commit(v, lambda p:p["choices"]["credentials"][0].update(purposes=["FOLDER_PROBE"]))
    calls = len(v.calls)
    with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): client.read()
    assert len(v.calls) == calls and v.settings.read().payload["operations"] == profile.payload["operations"]


def test_lost_normal_cas_is_unknown_once_and_read_inspects_existing_effect(fixture, monkeypatch):
    v = system(fixture, monkeypatch)
    client = v.port.authority(v.authority); observed = client.read(); value = desired(observed)
    v.state["reply"] = "lost"
    assert client.compare_replace(observed, value) is WriteResult.UNKNOWN
    assert v.state["writes"] == 1
    v.state["reply"] = "plain"
    assert client.read().document() == value and v.state["writes"] == 1


def test_exact_native_admission_context_does_not_fabricate_ready_or_role(fixture, monkeypatch):
    v = system(fixture, monkeypatch)
    actor = v.setup.installation_id
    leader = Leadership(v.port.authority(v.authority), actor=actor,
        enrollment={actor:"synthetic-native-runtime-computer"})
    store = native_settings(v.root.parent/"runtime-checkpoint", create=True, owner_authorized=True)
    cp = NativeCheckpoint(store, installation_id=v.setup.installation_id, binding=leader.backend.binding,
        create=True, owner_authorized=True)
    context = AdmissionContext(v.settings, cp, leader, v.checker, lambda:None, lambda:None)
    admission = ConfigurationAdmission(context)
    with pytest.raises(ConfigurationError, match="^ADMISSION_LEADERSHIP_UNKNOWN$"): admission.revision()
    assert not admission.status()["runtime_active"]
