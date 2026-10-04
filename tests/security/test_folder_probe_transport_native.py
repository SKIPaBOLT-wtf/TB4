"""Actual native Win/Linux handles/private images with synthetic proof replies.

These tests qualify native lifetime/selection/refusal, not SSH authentication.
The separate required Linux tests exercise the actual server and physical root.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sys
import threading

import pytest

from tb4.credential_contract import Outcome, Purpose
from tb4.credential_persistence import export_private, restore_private
from tb4.drive.commissioning import SetupSpec
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.drive.docs_authority import AuthorityError, document_bytes
from tb4.drive.folder_authority import FolderBinding
from tb4.drive.folder_first_run import RemoteFolderCommissioning
from tb4.drive.folder_probe import FolderProbe, probe_header
from tb4.drive.folder_probe_transport import ProbeEndpoint, CredentialProbeProcess, credential_probe_pair
from tb4.drive.folder_protocol import FolderAccess, flat_json
from tb4.drive.folder_transport import FixedProcess
from tb4.exchange_layout import Capacity, empty_document, encoded
from tb4.key_policy import KeyAccessError
from tb4.private_settings import native_settings, SettingsError
from tb4.commissioning_checks import CommissionedStorage
from tests.security.test_private_settings_native import fixture, protect_fixture, SUPPORTED

pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Actual Windows/Linux native fixed proof transport")
INSTALLATION = "00000000-0000-4000-8000-000000000230"
TARGET = "00000000-0000-4000-8000-000000000231"
DOMAIN = "00000000-0000-4000-8000-000000000232"
SPEC = SetupSpec(TARGET, DOMAIN, "a" * 64, INSTALLATION, "FOLDER_SQLITE_V1", Capacity(1, 1, 1, 1))
HANDLE = AuthorityHandle(TARGET, "a" * 64, None)
TRUST = "e" * 64
CANARY = b"synthetic-native-probe-key-never-report"


def native():
    if os.name == "nt":
        from tb4.windows_key_native import WindowsKeyNative
        return WindowsKeyNative()
    from tb4.linux_key_native import LinuxKeyNative
    return LinuxKeyNative()


def pinned_known(path):
    api = native()
    user = api.identity()
    with api.open_key(str(path), user.sid if os.name == "nt" else user.uid) as held:
        return held.version


def selection(store, resolver, path, *, purposes=frozenset({Purpose.FOLDER_PROBE}), expires=200):
    args = dict(interactive_required=False) if os.name == "nt" else dict(
        access_mode="existing_key", launch_mode="headless")
    ref = store.select(path=str(path), target_id=TARGET, target_trust=TRUST, purposes=purposes,
                       expires_at=expires, owner_authorized=True, **args)
    handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=ref, purposes=purposes,
                             expires_at=expires, owner_authorized=True)
    return handle


def document():
    value = empty_document(DOMAIN, SPEC.capacity)
    value["records"]["global.commissioning"] = dict(generation=0, operation_id=SPEC.setup_id,
        retention="RETAINED", body=SPEC.marker("STORAGE_READY"))
    return value


def response(request):
    return {**probe_header(FolderBinding(TARGET, DOMAIN), request["nonce"]), "result":"VERIFIED",
        "revision":7, "body":base64.b64encode(document_bytes(document())).decode("ascii"),
        "blueprint":SPEC.fingerprint, "authority":HANDLE.seal}


def system(fixture, monkeypatch, *, purposes=frozenset({Purpose.FOLDER_PROBE})):
    root, settings = fixture
    key, known = root.parent / "synthetic-key", root.parent / "synthetic-known"
    key.write_bytes(CANARY); known.write_bytes(b"synthetic-pinned-known-file")
    protect_fixture(key); protect_fixture(known)
    endpoint = ProbeEndpoint(TARGET, TRUST, str(Path(sys.executable).resolve()), "storage.invalid",
                             22222, "synthetic-user", str(known), pinned_known(known))
    now = [100]
    store, resolver = credential_probe_pair(INSTALLATION, endpoint, SPEC, HANDLE, clock=lambda:now[0])
    handle = selection(store, resolver, key, purposes=purposes)
    process = CredentialProbeProcess(resolver, handle)
    probe = FolderProbe(process, SPEC, HANDLE, FolderAccess(process.binding, True, True))
    calls = []
    def reply(transport, raw):
        request = flat_json(raw)
        calls.append((transport, request))
        return encoded(response(request))
    monkeypatch.setattr(FixedProcess, "call", reply)
    return root, settings, key, known, endpoint, now, store, resolver, handle, process, probe, calls


def request():
    return dict(purpose=Purpose.FOLDER_PROBE, target_id=TARGET, target_trust=TRUST)


def test_native_borrowed_paths_are_closed_and_public_fixed_use_never_returns_proof(fixture, monkeypatch, capsys):
    root, settings, key, known, _, _, store, resolver, handle, process, probe, calls = system(fixture, monkeypatch)
    settings.save({"registry":export_private(store,resolver),"history":{"kept":"UNKNOWN"}}, expected_revision=0)
    before = settings.read()
    api = store._native
    if os.name == "nt":
        from tb4.windows_key_native import HeldKey
    else:
        from tb4.linux_key_native import HeldKey
    original = HeldKey.process_path
    borrowed = []
    def path(held):
        value = original(held)
        borrowed.append((held, value))
        # TEST ONLY: prove the internal path names the exact borrowed contents.
        assert Path(value).read_bytes() in {CANARY, b"synthetic-pinned-known-file"}
        return value
    monkeypatch.setattr(HeldKey, "process_path", path)
    first, second = probe.verify(), probe.verify()
    assert first.document() == second.document() == document()
    assert len(calls) == 2 and calls[0][1]["nonce"] != calls[1][1]["nonce"]
    assert process._runner._pending is None
    for held, value in borrowed:
        with pytest.raises(KeyAccessError): _ = held.handle
        if os.name != "nt": assert not Path(value).exists()
    assert resolver.invoke(handle, **request()).report() == dict(
        outcome="DENIED", retry_automatically=False, inspection_required=False)
    assert len(calls) == 2
    report = resolver.capability(handle, **request()).report()
    assert report["available"] and all(v not in json.dumps(report) for v in (
        handle, str(key), str(known), TRUST, CANARY.decode()))
    assert key.read_bytes() == CANARY and native_settings(root).read() == before
    assert CANARY not in (root / "settings.json").read_bytes()
    assert not any(hasattr(process, method) for method in ("compare_replace","create","activate","run"))
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("change,expected", [
    ("key-version",Outcome.REVOKED), ("key-permission",Outcome.DENIED),
    ("known-version",Outcome.DENIED), ("known-permission",Outcome.DENIED),
    ("expired",Outcome.EXPIRED), ("revoked",Outcome.REVOKED)])
def test_native_prior_success_cannot_authorize_later_key_trust_or_binding_loss(fixture, monkeypatch, change, expected):
    _, settings, key, known, _, now, store, resolver, handle, process, probe, calls = system(fixture, monkeypatch)
    probe.verify()
    if change == "key-version": key.write_bytes(b"synthetic-changed-key")
    if change == "key-permission": protect_fixture(key, broad=True)
    if change == "known-version": known.write_bytes(b"synthetic-changed-known")
    if change == "known-permission": protect_fixture(known, broad=True)
    if change == "expired": now[0] = 200
    if change == "revoked": resolver.revoke(handle, owner_authorized=True)
    settings.save({"registry":export_private(store,resolver),"history":{"kept":"UNKNOWN"}}, expected_revision=0)
    before = settings.read()
    assert resolver.capability(handle, **request()).outcome is expected
    with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): probe.verify()
    assert len(calls) == 1 and process._runner._pending is None and settings.read() == before


def test_native_restart_keeps_same_registry_and_requires_a_new_credential_bound_proof(fixture, monkeypatch):
    root, settings, key, _, endpoint, now, store, resolver, handle, _, probe, calls = system(fixture, monkeypatch)
    probe.verify()
    image = export_private(store,resolver)
    settings.save({"registry":image,"history":{"kept":"UNKNOWN"}}, expected_revision=0)
    before = native_settings(root).read()
    new_store, new_resolver = credential_probe_pair(INSTALLATION, endpoint, SPEC, HANDLE, clock=lambda:now[0])
    restore_private(before.payload["registry"], new_store, new_resolver)
    new_process = CredentialProbeProcess(new_resolver, handle)
    new_probe = FolderProbe(new_process, SPEC, HANDLE, FolderAccess(new_process.binding, True, True))
    assert new_probe.verify().document() == document()
    assert len(calls) == 2 and calls[0][1]["nonce"] != calls[1][1]["nonce"]
    key.write_bytes(b"synthetic-after-restart-rotation")
    with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): new_probe.verify()
    assert len(calls) == 2 and native_settings(root).read() == before
    assert export_private(new_store,new_resolver) == image


@pytest.mark.parametrize("failure", ["lost", "unknown", "nonce", "extra", "replay"])
def test_native_lost_partial_or_replayed_reply_discards_private_slot_without_retry(fixture, monkeypatch, failure, capsys):
    _, _, _, _, _, _, _, _, _, process, probe, calls = system(fixture, monkeypatch)
    proof = probe.verify()
    old = response(calls[0][1])
    def bad(transport, raw):
        req = flat_json(raw); calls.append((transport,req))
        if failure == "lost": raise OSError("SYNTHETIC_PRIVATE_CANARY")
        reply = response(req)
        if failure == "unknown": reply["result"] = "UNKNOWN"
        if failure == "nonce": reply["nonce"] = "b" * 32
        if failure == "extra": reply["extra"] = "SYNTHETIC_PRIVATE_CANARY"
        if failure == "replay": reply = old
        return encoded(reply)
    monkeypatch.setattr(FixedProcess,"call",bad)
    with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$") as error: probe.verify()
    assert len(calls) == 2 and process._runner._pending is None
    assert "SYNTHETIC_PRIVATE_CANARY" not in str(error.value) and proof.document() == document()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("field,value", [("operation","CAS"),("extra","SYNTHETIC_PRIVATE_CANARY"),
                                        ("blueprint","b"*64),("authority","b"*64)])
def test_wrong_or_mutating_request_refuses_before_any_native_use(fixture, monkeypatch, field, value):
    _, _, _, _, _, _, store, _, _, process, _, calls = system(fixture,monkeypatch)
    monkeypatch.setattr(store._native,"open_key",lambda *_:pytest.fail("Forbidden request opened a credential"))
    raw={**probe_header(process.binding,"a"*32),"operation":"VERIFY",
         "blueprint":SPEC.fingerprint,"authority":HANDLE.seal,field:value}
    with pytest.raises(AuthorityError,match="^HELPER_UNAVAILABLE$"):process.call(encoded(raw))
    assert not calls and process._runner._pending is None


def test_parallel_private_slot_refuses_promptly_without_a_second_resolver_or_helper_use(fixture, monkeypatch):
    _, _, _, _, _, _, _, _, _, process, probe, calls = system(fixture,monkeypatch)
    entered, finish = threading.Event(), threading.Event()
    def waiting(transport,raw):
        req=flat_json(raw);calls.append((transport,req));entered.set()
        assert finish.wait(5), "Synthetic proof release missing"
        return encoded(response(req))
    monkeypatch.setattr(FixedProcess,"call",waiting)
    with ThreadPoolExecutor(1) as workers:
        first=workers.submit(probe.verify)
        try:
            assert entered.wait(5), "Synthetic proof did not start"
            with pytest.raises(AuthorityError,match="^PROBE_UNAVAILABLE$"):probe.verify()
            assert len(calls)==1
        finally:finish.set()
        assert first.result(timeout=5).document()==document()
    assert process._runner._pending is None


def test_fetcher_only_selected_key_cannot_be_used_for_private_folder_probe(fixture,monkeypatch):
    _, _, _, _, _, _, _, resolver, handle, process, probe, calls=system(
        fixture,monkeypatch,purposes=frozenset({Purpose.FETCHER_STATUS}))
    assert resolver.capability(handle,**request()).outcome is Outcome.DENIED
    with pytest.raises(AuthorityError,match="^PROBE_UNAVAILABLE$"):probe.verify()
    assert not calls and process._runner._pending is None


def test_exact_native_transport_enters_read_only_first_run_and_refuses_changed_pins(fixture,monkeypatch):
    _, _, _, _, endpoint, _, _, _, _, process, probe, calls=system(fixture,monkeypatch)
    port=RemoteFolderCommissioning(probe)
    record={"spec":asdict(SPEC),"authority":HANDLE.record()}
    assert CommissionedStorage(port).verify(record)==document()
    process._runner.endpoint=replace(endpoint,host="foreign.invalid")
    with pytest.raises(SettingsError,match="^STORAGE_UNAVAILABLE$"):CommissionedStorage(port).verify(record)
    assert len(calls)==1 and process._runner._pending is None
