"""Actual Windows/Linux private metadata; no external endpoint or credential use."""
import copy
from dataclasses import asdict, replace
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from tb4.commissioning_checks import native_credential_pair
from tb4.commissioning_state import Setup
from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.drive.commissioning import SetupSpec
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import FolderBinding
from tb4.drive.folder_endpoint import NativeFolderEndpoint
from tb4.drive.folder_probe_transport import ProbeEndpoint
from tb4.drive.folder_transport import FixedProcess
from tb4.exchange_layout import Capacity
from tb4.private_settings import native_settings, SettingsError
from tb4.reconfiguration_maintenance import sha
from tests.security.test_private_settings_native import fixture, protect_fixture, SUPPORTED
from tests.security.test_credential_persistence_native import Runner, TARGET, TRUST, CANARY

pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Actual Windows/Linux protected endpoint metadata")
ERRORS = (AuthorityError, SettingsError)
BINDING = FolderBinding("00000000-0000-4000-8000-000000000264",
    "00000000-0000-4000-8000-000000000265")


def system(fixture, monkeypatch):
    root, settings = fixture
    setup = Setup(settings, create=True)
    key = root.parent / "synthetic-endpoint-key"
    key.write_bytes(CANARY); protect_fixture(key)
    now = [100]
    store, resolver = native_credential_pair(setup.installation_id, runner=Runner(),
        clock=lambda: now[0])
    scopes = frozenset({Purpose.FOLDER_AUTHORITY, Purpose.FETCHER_STATUS})
    mode = dict(interactive_required=False) if os.name == "nt" else dict(
        access_mode="existing_key", launch_mode="headless")
    ref = store.select(path=str(key), target_id=TARGET, target_trust=TRUST,
        purposes=scopes, expires_at=200, owner_authorized=True, **mode)
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=ref,
        purposes=scopes, expires_at=200, owner_authorized=True)
    spec = SetupSpec(BINDING.root_id, BINDING.domain_id, "b"*64, setup.installation_id,
        "FOLDER_SQLITE_V1", Capacity(1,1,1,1))
    authority = AuthorityHandle(BINDING.root_id, "a"*64, None)
    setup.choose(dict(role="watchdog", network_scope=[],
        storage=dict(spec=asdict(spec), authority=authority.record())))
    selected = [dict(handle=handle, target_id=TARGET, target_trust=TRUST,
        purposes=[Purpose.FOLDER_AUTHORITY.value])]
    setup.persist_credentials(store, resolver, selected)
    metadata = native_settings(root.parent / "endpoint-metadata", create=True, owner_authorized=True)
    selection = NativeFolderEndpoint(metadata, setup.installation_id)
    endpoint = ProbeEndpoint(TARGET, TRUST, str(Path(sys.executable).resolve()), "storage.invalid",
        22222, "synthetic-user", str(root.parent / "synthetic-endpoint-known"), 7)
    def denied(*args, **kwargs):
        pytest.fail("metadata touched a credential-use or transport operation")
    monkeypatch.setattr(CredentialResolver, "invoke", denied)
    monkeypatch.setattr(FixedProcess, "call", denied)
    return SimpleNamespace(root=root, setup=setup, key=key, store=store, resolver=resolver,
        handle=handle, selected=selected, now=now, metadata=metadata, selection=selection,
        endpoint=endpoint, spec=spec, authority=authority)


def prepare(v):
    return v.selection.prepare(v.setup, v.endpoint, v.handle, owner_authorized=True)


def test_native_same_record_restart_lookup_preserves_profile_key_history_and_closed_status(fixture, monkeypatch, capsys):
    v = system(fixture, monkeypatch)
    before = v.setup.store.read()
    def denied(*args, **kwargs): pytest.fail("metadata opened a key")
    monkeypatch.setattr(v.store._native, "open_key", denied)
    reference = prepare(v)
    snap = v.metadata.read()
    assert snap.revision == 1 and snap.previous is None
    reopened = NativeFolderEndpoint(native_settings(v.metadata.native.root), v.setup.installation_id)
    profile = Setup(native_settings(v.root))
    facts = reopened.lookup(profile, reference)
    assert facts.reference == reference and facts.endpoint == v.endpoint and facts.credential_handle == v.handle
    assert facts.binding == BINDING and reopened.inspect() == dict(
        status="SELECTED", reference=reference, metadata_only=True, credential_ready=False)
    assert profile.store.read() == before and v.key.read_bytes() == CANARY
    raw = (v.metadata.native.root / "settings.json").read_bytes()
    assert CANARY not in raw and str(v.key).encode() not in raw
    with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_EXISTS$"): prepare(v)
    assert v.metadata.read() == snap and capsys.readouterr() == ("","")


@pytest.mark.parametrize("authorization", [False, 1, "yes"])
def test_native_selection_requires_exact_explicit_owner_authorization(fixture, monkeypatch, authorization):
    v = system(fixture, monkeypatch); before = v.setup.store.read()
    with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_OWNER_REQUIRED$"):
        v.selection.prepare(v.setup, v.endpoint, v.handle, owner_authorized=authorization)
    assert v.metadata.read() is None and v.setup.store.read() == before


@pytest.mark.parametrize("change", ["target", "trust"])
def test_native_wrong_selected_target_refuses_before_metadata_write(fixture, monkeypatch, change):
    v = system(fixture, monkeypatch)
    bad = replace(v.endpoint, **({"target_id": BINDING.root_id} if change=="target" else {"trust":"e"*64}))
    before = v.setup.store.read()
    with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_TARGET$"):
        v.selection.prepare(v.setup, bad, v.handle, owner_authorized=True)
    assert v.metadata.read() is None and v.setup.store.read() == before


@pytest.mark.parametrize("change", ["root", "domain", "setup", "actor", "capacity", "mode",
    "authority", "unselected", "non-folder-purpose", "saved-revocation"])
def test_native_saved_endpoint_cannot_override_later_protected_selection(fixture, monkeypatch, change):
    v = system(fixture, monkeypatch); reference = prepare(v); snap = v.metadata.read()
    storage = copy.deepcopy(v.setup.private_choices()["storage"])
    if change == "root": storage["spec"]["root_id"] = BINDING.domain_id
    if change == "domain": storage["spec"]["domain_id"] = BINDING.root_id
    if change == "setup": storage["spec"]["setup_id"] = "c"*64
    if change == "actor": storage["spec"]["bootstrap_actor"] = TARGET
    if change == "capacity": storage["spec"]["capacity"] = asdict(Capacity(2,1,1,1))
    if change == "mode": storage["spec"]["mode"] = "NATIVE_DOCS"
    if change == "authority": storage["authority"]["seal"] = "b"*64
    if change in {"root","domain","setup","actor","capacity","mode","authority"}:
        v.setup.choose({"storage":storage})
    if change == "unselected": v.setup.choose({"credentials":[]})
    if change == "non-folder-purpose":
        selected = copy.deepcopy(v.selected); selected[0]["purposes"] = [Purpose.FETCHER_STATUS.value]
        v.setup.choose({"credentials":selected})
    if change == "saved-revocation":
        v.resolver.revoke(v.handle, owner_authorized=True)
        v.setup.persist_credentials(v.store, v.resolver, v.selected)
    before = v.setup.store.read()
    with pytest.raises(ERRORS): v.selection.lookup(v.setup, reference)
    assert v.metadata.read() == snap and v.setup.store.read() == before


@pytest.mark.parametrize("loss", ["version", "permission", "expired"])
def test_native_metadata_does_not_grant_live_credential_readiness_or_reselect(fixture, monkeypatch, loss):
    v = system(fixture, monkeypatch); reference = prepare(v)
    before = v.setup.store.read(); snap = v.metadata.read()
    if loss == "version": v.key.write_bytes(b"synthetic-replacement")
    if loss == "permission": protect_fixture(v.key, broad=True)
    if loss == "expired": v.now[0] = 200
    facts = v.selection.lookup(v.setup, reference)
    assert facts.credential_handle == v.handle and not v.selection.inspect()["credential_ready"]
    outcome = v.resolver.capability(v.handle, purpose=Purpose.FOLDER_AUTHORITY,
        target_id=TARGET, target_trust=TRUST).outcome
    assert outcome in {Outcome.REVOKED, Outcome.DENIED, Outcome.EXPIRED}
    assert v.metadata.read() == snap and v.setup.store.read() == before


def test_native_wrong_reference_foreign_installation_and_changed_store_pin_refuse(fixture, monkeypatch):
    v = system(fixture, monkeypatch); reference = prepare(v)
    before = v.setup.store.read(); snap = v.metadata.read()
    with pytest.raises(AuthorityError): v.selection.lookup(v.setup, "fe_"+"f"*32)
    other = native_settings(v.root.parent / "other-profile", create=True, owner_authorized=True)
    foreign = Setup(other, create=True)
    with pytest.raises(AuthorityError): v.selection.lookup(foreign, reference)
    v.selection.store = v.setup.store
    with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_CHANGED$"): v.selection.lookup(v.setup, reference)
    assert v.metadata.read() == snap and v.setup.store.read() == before


def test_native_setup_alias_and_stale_snapshot_refuse_without_another_selection(fixture, monkeypatch):
    v = system(fixture, monkeypatch); before = v.setup.store.read()
    alias = NativeFolderEndpoint(v.setup.store, v.setup.installation_id)
    with pytest.raises(ERRORS): alias.prepare(v.setup, v.endpoint, v.handle, owner_authorized=True)
    assert v.setup.store.read() == before and v.metadata.read() is None
    other = Setup(native_settings(v.root)); other.choose({"network_scope":[]})
    newer = v.setup.store.read()
    with pytest.raises(SettingsError, match="CHANGED_RELOAD_REQUIRED"):
        prepare(v)
    assert v.setup.store.read() == newer and v.metadata.read() is None


@pytest.mark.parametrize("change", ["protection", "revision"])
def test_native_lost_metadata_protection_or_immutable_revision_refuses(fixture, monkeypatch, change):
    v = system(fixture, monkeypatch); reference = prepare(v); before = v.setup.store.read()
    if change == "protection": protect_fixture(v.metadata.native.root / "settings.json", broad=True)
    else:
        snap = v.metadata.read()
        v.metadata.save(snap.payload, expected_revision=1)
    with pytest.raises(ERRORS): v.selection.lookup(v.setup, reference)
    assert v.setup.store.read() == before


def test_native_held_endpoint_lock_cannot_create_or_change_profile(fixture, monkeypatch):
    v = system(fixture, monkeypatch); before = v.setup.store.read()
    with v.metadata.native.locked():
        with pytest.raises(SettingsError): prepare(v)
    assert v.metadata.read() is None and v.setup.store.read() == before


@pytest.mark.parametrize("crash", ["before-promote", "after-promote"])
def test_native_same_pending_or_completed_selection_inspected_without_reselection(fixture, monkeypatch, crash):
    v = system(fixture, monkeypatch); before = v.setup.store.read()
    with v.metadata.native.locked() as port: kind = type(port)
    original = kind.promote
    def lost(port):
        if sha(port.binding) == v.selection._binding:
            if crash == "after-promote": original(port)
            raise SettingsError("SYNTHETIC_NATIVE_COMMIT_REPLY_LOST")
        return original(port)
    monkeypatch.setattr(kind, "promote", lost)
    with pytest.raises(SettingsError): prepare(v)
    observed = v.selection.inspect(); reference = observed["reference"]
    assert observed["status"] == ("PENDING" if crash=="before-promote" else "SELECTED")
    with pytest.raises(ERRORS): prepare(v)
    monkeypatch.setattr(kind, "promote", original)
    assert v.selection.recover(v.setup, reference, owner_authorized=True) == "ENDPOINT_SELECTED"
    snap = v.metadata.read()
    assert snap.revision == 1 and snap.previous is None and snap.payload["reference"] == reference
    assert v.selection.lookup(v.setup, reference).endpoint == v.endpoint and v.setup.store.read() == before


def test_native_pending_cannot_be_promoted_after_profile_change(fixture, monkeypatch):
    v = system(fixture, monkeypatch)
    with v.metadata.native.locked() as port: kind = type(port)
    original = kind.promote
    def stop(port):
        if sha(port.binding) == v.selection._binding: raise SettingsError("SYNTHETIC_NATIVE_STOP")
        return original(port)
    monkeypatch.setattr(kind, "promote", stop)
    with pytest.raises(SettingsError): prepare(v)
    reference = v.selection.inspect()["reference"]
    pending = (v.metadata.native.root / "settings.pending").read_bytes()
    monkeypatch.setattr(kind, "promote", original)
    storage = copy.deepcopy(v.setup.private_choices()["storage"])
    storage["authority"]["seal"] = "b"*64; v.setup.choose({"storage":storage})
    before = v.setup.store.read()
    with pytest.raises(AuthorityError):
        v.selection.recover(v.setup, reference, owner_authorized=True)
    assert (v.metadata.native.root / "settings.pending").read_bytes() == pending
    assert not (v.metadata.native.root / "settings.json").exists() and v.setup.store.read() == before


def test_native_conflicting_pending_is_not_silently_repaired(fixture, monkeypatch):
    v = system(fixture, monkeypatch); reference = prepare(v); before = v.setup.store.read()
    with v.metadata.native.locked() as port:
        raw = port.read("settings.json"); port.stage(raw)
    pending = (v.metadata.native.root / "settings.pending").read_bytes()
    with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_RECOVERY_CONFLICT$"):
        v.selection.inspect()
    with pytest.raises(AuthorityError):
        v.selection.recover(v.setup, reference, owner_authorized=True)
    assert (v.metadata.native.root / "settings.pending").read_bytes() == pending
    assert (v.metadata.native.root / "settings.json").read_bytes() == raw
    assert v.setup.store.read() == before


def test_native_unknown_history_is_preserved_and_lookup_grants_no_activation(fixture, monkeypatch):
    v = system(fixture, monkeypatch)
    v.setup.perform_once("e"*64, lambda: None, owner_authorized=True)
    before = v.setup.store.read(); reference = prepare(v)
    assert v.selection.lookup(v.setup, reference).credential_handle == v.handle
    assert v.setup.store.read() == before and v.setup._payload["operations"] == {"e"*64:"UNKNOWN"}
    assert v.setup.status()["reason"] == "UNKNOWN_OPERATION" and not v.setup.status()["runtime_active"]
