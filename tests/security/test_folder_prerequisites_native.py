"""Actual protected native profiles and keys with synthetic fixed proof replies."""
import copy
from pathlib import Path

import pytest

from tb4.commissioning_checks import CommissionedStorage, Prerequisites, detect_environment
from tb4.commissioning_state import DenyActivation, Setup, Validation
from tb4.credential_contract import CredentialResolver, Purpose
from tb4.drive.folder_first_run import RemoteFolderCommissioning
from tb4.drive.folder_prerequisites import native_folder_prerequisites
from tb4.drive.folder_transport import FixedProcess
from tb4.private_settings import SettingsError, native_settings
from tests.security.test_ballpark_contract import fixture as descriptor
from tests.security.test_first_run import Source, FACTS
from tests.security.test_folder_connection_native import system as connected, commit, saved
from tests.security.test_private_settings_native import fixture, protect_fixture, SUPPORTED

pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Actual native Folder first-run")


def system(fixture, monkeypatch, *, source=None, credential_factory=None):
    v = connected(fixture, monkeypatch)
    local = descriptor()
    local.update(installation_id=v.setup.installation_id, domain_id=v.spec.domain_id)
    commit(v, lambda p:p["choices"].update(descriptor=local))
    v.setup = Setup(native_settings(v.root))
    v.source = Source() if source is None else source
    v.checker = native_folder_prerequisites(native_settings(v.root), access=v.access,
        environment=lambda:detect_environment(launch_mode="DESKTOP_SESSION"),
        source=v.source, runtime=FACTS, clock=lambda:v.now[0],
        credential_factory=credential_factory)
    return v


def test_actual_first_run_restart_and_default_activation_keep_identity_image_history(fixture, monkeypatch, capsys):
    v = system(fixture, monkeypatch)
    before = v.settings.read()
    def forbidden(*_args, **_kwargs): pytest.fail("First-run selected or enrolled a key")
    monkeypatch.setattr(v.store.__class__, "select", forbidden)
    monkeypatch.setattr(CredentialResolver, "enroll", forbidden)
    assert type(v.checker) is Prerequisites and type(v.checker.storage) is CommissionedStorage
    assert type(v.checker.storage.port) is RemoteFolderCommissioning
    with monkeypatch.context() as guard:
        guard.setattr(v.settings.__class__, "_save_locked", forbidden)
        assert type(v.checker.validate(before.payload)) is Validation
        assert v.settings.read() == before
    assert v.setup.review(v.checker)["settings_validated"]
    ready = v.settings.read()
    assert ready.previous == before.payload
    assert {k:x for k,x in ready.payload.items() if k not in {"state","reason"}} == {
        k:x for k,x in before.payload.items() if k not in {"state","reason"}}
    restarted = Setup(native_settings(v.root))
    assert not restarted.status()["settings_validated"]
    assert restarted.review(v.checker)["settings_validated"]
    assert restarted.activate(v.checker, DenyActivation())["reason"] == "ACTIVATION_NOT_AUTHORIZED"
    assert v.settings.read().payload["credential_image"] == before.payload["credential_image"]
    assert v.settings.read().payload["operations"] == before.payload["operations"]
    assert v.state["writes"] == 0 and capsys.readouterr() == ("","")


@pytest.mark.parametrize("change", ["unselected", "revoked", "selection-revoked",
    "key-version", "known-version", "key-permission", "known-permission", "expired"])
def test_prior_validation_does_not_hide_current_native_loss(fixture, monkeypatch, change):
    v = system(fixture, monkeypatch)
    assert type(v.checker.validate(v.settings.read().payload)) is Validation
    if change == "unselected": commit(v, lambda p:p["choices"].update(credentials=[]))
    if change == "revoked": commit(v, lambda p:p["credential_image"]["bindings"][v.handle].update(revoked=True))
    if change == "selection-revoked":
        locator = v.resolver._bindings[v.handle].store_locator
        commit(v, lambda p:p["credential_image"]["selections"][locator].update(revoked=True))
    if change == "key-version": v.key.write_bytes(b"synthetic-replaced-key")
    if change == "known-version": v.known.write_bytes(b"synthetic-replaced-known")
    if change == "key-permission": protect_fixture(v.key, broad=True)
    if change == "known-permission": protect_fixture(v.known, broad=True)
    if change == "expired": v.now[0] = 200
    before, calls = saved(v), len(v.calls)
    def forbidden(*_args, **_kwargs): pytest.fail("Refused first-run reached transport")
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    with pytest.raises(SettingsError): v.checker.validate(v.settings.read().payload)
    assert v.checker.credentials is None and saved(v) == before and len(v.calls) == calls


@pytest.mark.parametrize("change", ["history", "descriptor", "image"])
def test_forged_caller_payload_is_refused_before_proof_or_key_io(fixture, monkeypatch, change):
    v = system(fixture, monkeypatch)
    before = saved(v); payload = copy.deepcopy(before[0].payload)
    if change == "history": payload["operations"]["a"*64] = "CONFIRMED"
    if change == "descriptor": payload["choices"]["descriptor"]["revision"] += 1
    if change == "image": payload["credential_image"]["bindings"][v.handle]["expires_at"] -= 1
    def forbidden(*_args, **_kwargs): pytest.fail("Mismatched payload reached key or proof")
    monkeypatch.setattr(v.store._native.__class__, "open_key", forbidden)
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"): v.checker.validate(payload)
    assert saved(v) == before and not v.calls and v.checker.credentials is None


def test_constructor_has_no_key_proof_selection_or_profile_write(fixture, monkeypatch):
    v = system(fixture, monkeypatch); before = saved(v)
    def forbidden(*_args, **_kwargs): pytest.fail("First-run constructor used a key, proof or save")
    monkeypatch.setattr(v.store._native.__class__, "open_key", forbidden)
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    monkeypatch.setattr(v.settings.__class__, "_save_locked", forbidden)
    checker = native_folder_prerequisites(native_settings(v.root), access=v.access,
        environment=lambda:detect_environment(launch_mode="DESKTOP_SESSION"),
        source=v.source, runtime=FACTS, clock=lambda:v.now[0])
    assert type(checker) is Prerequisites and checker.credentials is None
    assert saved(v) == before and not v.calls


def test_trusted_native_factory_restores_same_image_twice_without_new_handles(fixture, monkeypatch):
    v = system(fixture, monkeypatch); before = saved(v); calls = []
    def factory(installation):
        assert installation == v.setup.installation_id
        calls.append(installation)
        return v.pair()
    checker = native_folder_prerequisites(native_settings(v.root), access=v.access,
        environment=lambda:detect_environment(launch_mode="DESKTOP_SESSION"),
        source=v.source, runtime=FACTS, clock=lambda:v.now[0], credential_factory=factory)
    assert type(checker.validate(before[0].payload)) is Validation
    assert calls == [v.setup.installation_id]*2 and saved(v) == before and len(v.calls) == 1


@pytest.mark.parametrize("result", [None, ({}, {})])
def test_untyped_credential_factory_refuses_before_proof(fixture, monkeypatch, result):
    v = system(fixture, monkeypatch); before = saved(v)
    checker = native_folder_prerequisites(native_settings(v.root), access=v.access,
        environment=lambda:detect_environment(launch_mode="DESKTOP_SESSION"),
        source=v.source, runtime=FACTS, clock=lambda:v.now[0],
        credential_factory=lambda _installation:result)
    with pytest.raises(SettingsError, match="^CREDENTIAL_UNAVAILABLE$"):
        checker.validate(before[0].payload)
    assert saved(v) == before and not v.calls and checker.credentials is None


def test_explicit_current_probe_scope_is_required_despite_broader_saved_image(fixture, monkeypatch):
    v = system(fixture, monkeypatch)
    commit(v, lambda p:p["choices"]["credentials"][0].update(purposes=[Purpose.FOLDER_AUTHORITY.value]))
    before = saved(v)
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"): v.checker.validate(before[0].payload)
    assert saved(v) == before and not v.calls


def test_local_unknown_remains_blocked_for_setup_without_becoming_an_election_barrier(fixture, monkeypatch):
    v = system(fixture, monkeypatch)
    commit(v, lambda p:p["operations"].update({"e"*64:"UNKNOWN"}))
    setup = Setup(native_settings(v.root)); before = v.settings.read()
    assert setup.review(v.checker)["reason"] == "UNKNOWN_OPERATION"
    after = v.settings.read()
    assert after.payload["operations"] == before.payload["operations"]
    assert after.payload["credential_image"] == before.payload["credential_image"] and not v.calls
    assert v.connection.authority_client(v.access).read()
    assert v.settings.read() == after and v.state["writes"] == 0


@pytest.mark.parametrize("part", ["environment", "descriptor", "instructions"])
def test_original_first_run_gates_are_not_replaced_by_native_storage_proof(fixture, monkeypatch, part):
    source = Source(); v = system(fixture, monkeypatch, source=source)
    if part == "environment":
        from tb4.commissioning_checks import Environment
        checker = native_folder_prerequisites(native_settings(v.root), access=v.access,
            environment=lambda:Environment("OTHER","OTHER","USER","EXTERNAL","UNQUALIFIED"),
            source=source, runtime=FACTS, clock=lambda:v.now[0])
    else: checker = v.checker
    if part == "descriptor": commit(v, lambda p:p["choices"].update(descriptor=None))
    if part == "instructions": source.fail = True
    before = saved(v)
    code = {"environment":"ENVIRONMENT_UNAVAILABLE", "descriptor":"DESCRIPTOR_REQUIRED",
            "instructions":"INSTRUCTIONS_UNAVAILABLE"}[part]
    with pytest.raises(SettingsError, match="^"+code+"$"): checker.validate(before[0].payload)
    assert saved(v) == before and checker.credentials is None and v.state["writes"] == 0


@pytest.mark.parametrize("which", ["profile", "endpoint"])
def test_existing_pending_is_preserved_without_recovery_or_transport(fixture, monkeypatch, which):
    v = system(fixture, monkeypatch)
    store = v.settings if which == "profile" else v.metadata
    with store.native.locked() as port: port.stage(b"synthetic-incomplete-pending")
    before = (Path(store.native.root)/"settings.pending").read_bytes()
    def forbidden(*_args, **_kwargs): pytest.fail("Pending first-run reached proof")
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"):
        v.checker.validate(v.setup._payload)
    assert (Path(store.native.root)/"settings.pending").read_bytes() == before and not v.calls


@pytest.mark.parametrize("loss", ["expiry", "key-version", "known-version"])
def test_native_loss_during_instruction_check_refuses_returned_validation(fixture, monkeypatch, loss):
    source = Source()
    v = system(fixture, monkeypatch, source=source)
    before = v.settings.read()
    original = source.resolve
    def change(*args):
        if loss == "expiry": v.now[0] = 200
        if loss == "key-version": v.key.write_bytes(b"synthetic-late-key")
        if loss == "known-version": v.known.write_bytes(b"synthetic-late-known")
        return original(*args)
    source.resolve = change
    with pytest.raises(SettingsError, match="^CREDENTIAL_UNAVAILABLE$"):
        v.checker.validate(before.payload)
    assert v.settings.read() == before and len(v.calls) == 1 and v.state["writes"] == 0
    assert v.checker.credentials is None


@pytest.mark.parametrize("phase", ["instructions", "final-factory"])
def test_valid_protected_frame_change_during_review_cannot_grant_readiness(fixture, monkeypatch, phase):
    source = Source(); v = system(fixture, monkeypatch, source=source)
    before = v.settings.read(); calls = []
    def mutate():
        commit(v, lambda p:p["operations"].update({"c"*64:"CONFIRMED"}))
    if phase == "instructions":
        original = source.resolve
        def change(*args):
            mutate()
            return original(*args)
        source.resolve = change
    else:
        def factory(installation):
            assert installation == v.setup.installation_id
            calls.append(1)
            if len(calls) == 2: mutate()
            return v.pair()
        v.checker = native_folder_prerequisites(native_settings(v.root), access=v.access,
            environment=lambda:detect_environment(launch_mode="DESKTOP_SESSION"),
            source=source, runtime=FACTS, clock=lambda:v.now[0], credential_factory=factory)
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"):
        v.checker.validate(before.payload)
    assert v.settings.read().payload["operations"]["c"*64] == "CONFIRMED"
    assert len(v.calls) == 1 and v.checker.credentials is None and v.state["writes"] == 0


@pytest.mark.parametrize("field", ["source", "storage", "environment", "clock", "native_folder",
    "cleared-native-folder", "cleared-guard-required"])
def test_mutated_trusted_composition_is_refused_before_key_or_proof(fixture, monkeypatch, field):
    v = system(fixture, monkeypatch); before = saved(v)
    if field == "cleared-native-folder": v.checker._native_folder = None
    elif field == "cleared-guard-required": v.checker._native_folder_required = False
    else: setattr(v.checker, "_native_folder" if field == "native_folder" else field, object())
    def forbidden(*_args, **_kwargs): pytest.fail("Mutated composition reached native key or proof")
    monkeypatch.setattr(v.store._native.__class__, "open_key", forbidden)
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"):
        v.checker.validate(before[0].payload)
    assert saved(v) == before and not v.calls and v.checker.credentials is None
