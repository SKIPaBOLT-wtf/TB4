"""Actual Windows/Linux selection freshness with synthetic closed wire replies.

Native profile/key protection is real. Authenticated SSH is qualified separately.
"""
import base64
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tb4.commissioning_state import Setup, validated
from tb4.credential_contract import CredentialResolver, Purpose
from tb4.credential_persistence import export_private
from tb4.drive.commissioning import SetupSpec
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.drive.docs_authority import AuthorityError, WriteResult, document_bytes
from tb4.drive.folder_connection import (
    NativeFolderConnection, NativeFolderProbeProcess, NativeFolderAuthorityProcess)
from tb4.drive.folder_endpoint import NativeFolderEndpoint
from tb4.drive.folder_endpoint_attachment import NativeFolderEndpointAttachment
from tb4.drive.folder_first_run import RemoteFolderCommissioning
from tb4.drive.folder_probe import probe_header
from tb4.drive.folder_protocol import FolderAccess, flat_json, header
from tb4.drive.folder_transport import FixedProcess
from tb4.exchange_layout import Capacity, encoded
from tb4.private_settings import native_settings, SettingsError
from tb4.timing_contract import TimingProfile
from tests.security.test_private_settings_native import fixture, protect_fixture, SUPPORTED
from tests.security.test_folder_authority_transport_native import (
    system as transport_system, INSTALLATION, TARGET, TRUST, BINDING, CANARY, desired)

pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Actual protected native Folder connection")
SCOPES = frozenset({Purpose.FOLDER_PROBE, Purpose.FOLDER_AUTHORITY})


def system(fixture, monkeypatch):
    v = transport_system(fixture, monkeypatch, purposes=SCOPES)
    spec = SetupSpec(BINDING.root_id, BINDING.domain_id, "b"*64,
                     INSTALLATION, "FOLDER_SQLITE_V1", Capacity(1, 1, 1, 1))
    authority = AuthorityHandle(BINDING.root_id, "a"*64, None)
    storage = dict(spec=asdict(spec), authority=authority.record())
    selected = [dict(handle=v.handle, target_id=TARGET, target_trust=TRUST,
                     purposes=sorted(p.value for p in SCOPES))]
    payload = dict(schema_version=1, installation_id=INSTALLATION, setup_nonce="9"*64,
        state="INCOMPLETE", reason="REVALIDATION_REQUIRED",
        choices=dict(role="watchdog", storage=storage, storage_request=None, network_scope=[],
            credentials=selected, descriptor=None, timing=asdict(TimingProfile())),
        operations={}, credential_image=export_private(v.store, v.resolver))
    v.settings.save(validated(payload), expected_revision=0)
    v.setup = Setup(v.settings)
    v.spec, v.authority, v.storage = spec, authority, storage
    v.state["document"]["records"]["global.commissioning"] = dict(generation=0,
        operation_id=spec.setup_id, retention="RETAINED", body=spec.marker("STORAGE_READY"))
    v.metadata_root = v.root.parent / "owned-fresh-folder-endpoint"
    v.metadata = native_settings(v.metadata_root, create=True, owner_authorized=True)
    v.selection = NativeFolderEndpoint(v.metadata, INSTALLATION)
    v.reference = v.selection.prepare(v.setup, v.endpoint, v.handle, owner_authorized=True)
    NativeFolderEndpointAttachment(v.selection, v.settings).attach(
        v.setup, v.reference, owner_authorized=True)
    original = v.wire
    def wire(transport, raw):
        request = flat_json(raw)
        if request["operation"] != "VERIFY":
            return original(transport, raw)
        v.calls.append((transport, request))
        return encoded({**probe_header(BINDING, request["nonce"]), "result":"VERIFIED",
            "revision":v.state["revision"],
            "body":base64.b64encode(document_bytes(v.state["document"])).decode("ascii"),
            "blueprint":spec.fingerprint, "authority":authority.seal})
    v.wire = wire
    monkeypatch.setattr(FixedProcess, "call", wire)
    v.connection = NativeFolderConnection(native_settings(v.root), clock=lambda:v.now[0])
    v.access = FolderAccess(BINDING, True, True)
    v.client = v.connection.authority_client(v.access)
    v.probe = v.connection.probe(v.access)
    return v


def saved(v):
    return v.settings.read(), v.metadata.read(), v.key.read_bytes()


def commit(v, change):
    current = v.settings.read()
    payload = copy.deepcopy(current.payload)
    change(payload)
    v.settings.save(validated(payload), expected_revision=current.revision)


def test_native_constructor_and_each_operation_preserve_profile_image_history_and_key(fixture, monkeypatch, capsys):
    v = system(fixture, monkeypatch)
    before = saved(v)
    def forbidden(*_args, **_kwargs):
        pytest.fail("Connection selected, enrolled or rewrote an existing profile")
    monkeypatch.setattr(v.store.__class__, "select", forbidden)
    monkeypatch.setattr(CredentialResolver, "enroll", forbidden)
    monkeypatch.setattr(v.settings.__class__, "_save_locked", forbidden)
    with monkeypatch.context() as guard:
        guard.setattr(v.store._native.__class__, "open_key", forbidden)
        restarted = NativeFolderConnection(native_settings(v.root), clock=lambda:v.now[0])
    assert not v.calls and saved(v) == before
    probe, client = restarted.probe(v.access), restarted.authority_client(v.access)
    proof = probe.verify()
    assert RemoteFolderCommissioning(probe).verify(v.storage) == proof.document()
    first = client.read()
    value = desired(first)
    assert client.compare_replace(first, value) is WriteResult.ACCEPTED
    assert client.read().document() == value and probe.verify().document() == value
    assert saved(v) == before and v.state["writes"] == 1
    assert [request["operation"] for _, request in v.calls] == ["VERIFY", "VERIFY", "READ", "CAS", "READ", "VERIFY"]
    assert CANARY not in (v.root / "settings.json").read_bytes() and capsys.readouterr() == ("", "")


def frames(v):
    return tuple((root/name).read_bytes() if (root/name).exists() else None
        for root in (v.root, v.metadata_root) for name in ("settings.json", "settings.pending"))


def test_native_existing_pending_profile_is_held_without_recovery_or_transport(fixture, monkeypatch):
    v = system(fixture, monkeypatch)
    with v.settings.native.locked() as port:
        current = v.settings._decode(port.read("settings.json"), port.binding)
        frame = dict(schema_version=1, binding=port.binding, revision=current.revision+1,
            payload=current.payload, previous=current.payload)
        frame["digest"] = hashlib.sha256(encoded(frame)).hexdigest()
        port.stage(encoded(frame))
    before = frames(v)
    with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): v.client.read()
    with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): v.probe.verify()
    with pytest.raises(SettingsError): NativeFolderConnection(native_settings(v.root), clock=lambda:100)
    assert not v.calls and frames(v) == before


def test_native_changed_immutable_endpoint_frame_is_refused_without_repair(fixture, monkeypatch):
    v = system(fixture, monkeypatch)
    payload = v.metadata.read().payload
    v.metadata.save(payload, expected_revision=1)
    before = frames(v)
    with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): v.client.read()
    assert not v.calls and frames(v) == before


@pytest.mark.parametrize("which", ["profile", "endpoint"])
def test_native_hardlinked_frame_is_never_a_selection_grant(fixture, monkeypatch, which):
    v = system(fixture, monkeypatch)
    path = (v.root if which == "profile" else v.metadata_root) / "settings.json"
    alias = v.root.parent / "owned-connection-unsafe-frame-alias"
    os.link(path, alias)
    try:
        before = frames(v)
        with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): v.client.read()
        assert path.stat().st_nlink == 2 and not v.calls and frames(v) == before
    finally:
        alias.unlink()


@pytest.mark.parametrize("change", ["pointer", "endpoint", "profile", "clock"])
def test_native_mutated_cached_pins_are_refused_before_native_io(fixture, monkeypatch, change):
    v = system(fixture, monkeypatch)
    if change == "pointer": v.connection._pointer["reference"] = "fe_"+"f"*32
    if change == "endpoint": v.connection.endpoint = object()
    if change == "profile": v.connection.profile = v.metadata
    if change == "clock": v.connection._clock = lambda:101
    def forbidden(*_args, **_kwargs): pytest.fail("Changed pins reached native IO")
    monkeypatch.setattr(v.connection._link, "_pair", forbidden)
    with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): v.client.read()
    assert not v.calls


def test_native_untyped_store_or_connection_never_acquires_protected_io(fixture, monkeypatch):
    v = system(fixture, monkeypatch); before = saved(v)
    for value in (None, object(), SimpleNamespace()):
        with pytest.raises(AuthorityError, match="^FOLDER_CONNECTION_PROFILE$"):
            NativeFolderConnection(value, clock=lambda:100)
        for kind in (NativeFolderProbeProcess, NativeFolderAuthorityProcess):
            with pytest.raises(AuthorityError, match="^FOLDER_CONNECTION_PROCESS$"): kind(value)
    assert not v.calls and saved(v) == before



@pytest.mark.parametrize("selected,denied", [
    (Purpose.FOLDER_PROBE, Purpose.FOLDER_AUTHORITY),
    (Purpose.FOLDER_AUTHORITY, Purpose.FOLDER_PROBE)])
def test_native_restored_hidden_scope_cannot_override_explicit_current_selection(fixture, monkeypatch, selected, denied):
    v = system(fixture, monkeypatch)
    assert v.probe.verify() and v.client.read()
    commit(v, lambda payload:payload["choices"]["credentials"][0].update(purposes=[selected.value]))
    before, count = saved(v), len(v.calls)
    if denied is Purpose.FOLDER_PROBE:
        with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): v.probe.verify()
        assert v.client.read()
    else:
        with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): v.client.read()
        assert v.probe.verify()
    assert len(v.calls) == count + 1 and saved(v) == before


@pytest.mark.parametrize("change", [
    "unselected", "revoked", "selection-revoked", "key-version", "known-version",
    "key-permission", "known-permission", "expired"])
def test_native_success_never_grants_later_access_after_current_credential_or_trust_loss(fixture, monkeypatch, change):
    v = system(fixture, monkeypatch)
    old = v.client.read(); assert v.probe.verify()
    if change == "unselected": commit(v, lambda p:p["choices"].update(credentials=[]))
    if change == "revoked": commit(v, lambda p:p["credential_image"]["bindings"][v.handle].update(revoked=True))
    if change == "selection-revoked":
        locator = v.resolver._bindings[v.handle].store_locator
        commit(v, lambda p:p["credential_image"]["selections"][locator].update(revoked=True))
    if change == "key-version": v.key.write_bytes(b"synthetic-later-key")
    if change == "known-version": v.known.write_bytes(b"synthetic-later-known")
    if change == "key-permission": protect_fixture(v.key, broad=True)
    if change == "known-permission": protect_fixture(v.known, broad=True)
    if change == "expired": v.now[0] = 200
    before, count = saved(v), len(v.calls)
    with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): v.probe.verify()
    with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): v.client.read()
    assert v.client.compare_replace(old, desired(old)) is WriteResult.UNKNOWN
    assert len(v.calls) == count and saved(v) == before and v.state["writes"] == 0


@pytest.mark.parametrize("purpose", [Purpose.FOLDER_PROBE, Purpose.FOLDER_AUTHORITY])
@pytest.mark.parametrize("change", ["operation", "root", "nonce", "extra", "raw-type", "duplicate"])
def test_native_closed_request_rejection_precedes_every_profile_or_key_io(fixture, monkeypatch, purpose, change):
    v = system(fixture, monkeypatch)
    process = NativeFolderProbeProcess(v.connection) if purpose is Purpose.FOLDER_PROBE else NativeFolderAuthorityProcess(v.connection)
    value = dict(probe_header(BINDING, "a"*32), operation="VERIFY",
        blueprint=v.spec.fingerprint, authority=v.authority.seal) if purpose is Purpose.FOLDER_PROBE else dict(
        header(BINDING, "a"*32), operation="READ")
    if change == "operation": value["operation"] = "CAS" if purpose is Purpose.FOLDER_PROBE else "VERIFY"
    if change == "root": value["root"] = "00000000-0000-4000-8000-000000000999"
    if change == "nonce": value["nonce"] = "invalid"
    if change == "extra": value["extra"] = True
    raw = encoded(value)
    if change == "raw-type": raw = "synthetic-not-bytes"
    if change == "duplicate": raw = b'{"operation":"READ","operation":"VERIFY"}'
    def forbidden(*_args, **_kwargs): pytest.fail("Invalid request reached protected native IO")
    monkeypatch.setattr(v.connection._link, "_pair", forbidden)
    with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): process.call(raw)
    assert not v.calls


@pytest.mark.parametrize("change", ["reference", "root", "binding_digest", "null"])
def test_native_changed_current_pointer_never_reuses_previously_constructed_connection(fixture, monkeypatch, change):
    v = system(fixture, monkeypatch); assert v.client.read()
    def mutate(payload):
        if change == "null": payload["folder_endpoint"] = None
        elif change == "reference": payload["folder_endpoint"]["reference"] = "fe_"+"f"*32
        elif change == "root": payload["folder_endpoint"]["root"] = str(v.root)
        else: payload["folder_endpoint"]["binding_digest"] = "f"*64
    commit(v, mutate)
    before, count = saved(v), len(v.calls)
    with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): v.client.read()
    with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): v.probe.verify()
    assert saved(v) == before and len(v.calls) == count


@pytest.mark.parametrize("which", ["profile", "endpoint"])
def test_native_held_lock_refuses_immediately_without_transport_or_profile_change(fixture, monkeypatch, which):
    v = system(fixture, monkeypatch); before = saved(v)
    store = v.settings if which == "profile" else v.metadata
    with store.native.locked():
        with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): v.client.read()
    assert not v.calls and saved(v) == before


def test_native_lost_reply_after_cas_is_unknown_once_then_read_inspects_same_effect(fixture, monkeypatch):
    v = system(fixture, monkeypatch); old = v.client.read(); value = desired(old)
    before = saved(v)
    v.state["reply"] = "lost"
    assert v.client.compare_replace(old, value) is WriteResult.UNKNOWN
    assert len(v.calls) == 2 and v.state["writes"] == 1
    assert v.client.read().document() == value
    assert len(v.calls) == 3 and saved(v) == before


@pytest.mark.parametrize("operation", ["READ", "CAS"])
def test_native_changed_protected_frame_after_reply_is_not_returned_as_success(fixture, monkeypatch, operation):
    v = system(fixture, monkeypatch); old = v.client.read(); count = len(v.calls)
    original, path = v.wire, v.root / "settings.json"
    def reply_then_change(transport, raw):
        reply = original(transport, raw)
        # Only this owned synthetic frame changes; its native checksum remains
        # valid so the per-call postcondition, rather than decoding, must refuse.
        frame = json.loads(path.read_bytes())
        frame["payload"]["reason"] = "MISSING_CHOICES"
        frame.pop("digest")
        frame["digest"] = hashlib.sha256(encoded(frame)).hexdigest()
        path.write_bytes(encoded(frame))
        return reply
    monkeypatch.setattr(FixedProcess, "call", reply_then_change)
    if operation == "READ":
        with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): v.client.read()
        assert v.state["writes"] == 0
    else:
        assert v.client.compare_replace(old, desired(old)) is WriteResult.UNKNOWN
        assert v.state["writes"] == 1
    assert len(v.calls) == count + 1 and v.settings.read().payload["reason"] == "MISSING_CHOICES"


def test_native_local_unknown_history_does_not_block_existing_proof_or_authority(fixture, monkeypatch):
    v = system(fixture, monkeypatch)
    def unresolved(payload):
        payload.update(state="BLOCKED", reason="UNKNOWN_OPERATION")
        payload["operations"]["d"*64] = "UNKNOWN"
    commit(v, unresolved)
    before = saved(v)
    assert v.probe.verify() and v.client.read()
    assert saved(v) == before and v.settings.read().payload["operations"] == {"d"*64:"UNKNOWN"}



