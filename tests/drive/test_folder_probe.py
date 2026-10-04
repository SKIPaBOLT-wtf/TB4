"""Portable protocol tests. Synthetic replies do not qualify physical storage."""
import base64
from dataclasses import replace
from pathlib import Path
import sys

import pytest

from tb4.drive.commissioning import SetupSpec
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.drive.docs_authority import AuthorityError, document_bytes
from tb4.drive.folder_authority import FolderConfig
from tb4.drive.folder_probe import FolderProbe, handle_probe, probe_header
from tb4.drive.folder_protocol import FolderAccess, flat_json, handle
from tb4.drive.folder_transport import FixedProcess
from tb4.exchange_layout import Capacity, empty_document, encoded
from folder_fixtures import BINDING, DOMAIN
from test_folder_protocol import SyntheticPort
from test_native_leadership import ACTORS, tid

SPEC = SetupSpec(BINDING.root_id, DOMAIN, tid("probe-setup"), ACTORS[0],
                 "FOLDER_SQLITE_V1", Capacity(1, 1, 1, 1))
HANDLE = AuthorityHandle(BINDING.root_id, "a" * 64, None)


def document():
    value = empty_document(DOMAIN, SPEC.capacity)
    value["records"]["global.commissioning"] = dict(generation=0,
        operation_id=SPEC.setup_id, retention="RETAINED", body=SPEC.marker("STORAGE_READY"))
    return value


def client(monkeypatch, transform=lambda value: value):
    calls = []
    def call(_transport, raw):
        request = flat_json(raw); calls.append(request)
        reply = {**probe_header(BINDING, request["nonce"]), "result": "VERIFIED",
            "revision": 7, "body": base64.b64encode(document_bytes(document())).decode("ascii"),
            "blueprint": SPEC.fingerprint, "authority": HANDLE.seal}
        return encoded(transform(reply))
    monkeypatch.setattr(FixedProcess, "call", call)
    transport = FixedProcess(BINDING, (sys.executable,))
    return FolderProbe(transport, SPEC, HANDLE, FolderAccess(BINDING, True, True)), calls


def test_portable_exact_observation_is_fresh_and_has_no_mutating_api(monkeypatch):
    probe, calls = client(monkeypatch)
    first, second = probe.verify(), probe.verify()
    assert first.document() == second.document() == document()
    assert first.revision == 7 and first.spec == SPEC and first.handle == HANDLE
    assert first._origin is second._origin is probe._origin
    assert calls[0]["nonce"] != calls[1]["nonce"]
    assert all(set(r) == set(probe_header(BINDING, "")) |
               {"operation", "blueprint", "authority"} for r in calls)
    assert not any(hasattr(probe, k) for k in ("create", "compare_replace", "activate", "seed"))


@pytest.mark.parametrize("field,value", [
    ("root", DOMAIN), ("domain", BINDING.root_id), ("nonce", "b" * 32),
    ("mode", "FOLDER_SQLITE_V1"), ("version", 2), ("revision", True),
    ("revision", 0), ("revision", 2**80), ("body", "***"),
    ("body", base64.b64encode(document_bytes(empty_document(DOMAIN, SPEC.capacity))).decode("ascii")),
    ("blueprint", "b" * 64), ("authority", "b" * 64),
    ("extra", "SYNTHETIC_PRIVATE_CANARY"), ("result", "SNAPSHOT"), ("result", "UNKNOWN")])
def test_foreign_replayed_partial_or_malformed_reply_refuses_without_retry(monkeypatch, field, value):
    probe, calls = client(monkeypatch, lambda r: {**r, field: value})
    with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"):
        probe.verify()
    assert len(calls) == 1


def test_saved_reply_cannot_qualify_next_observation(monkeypatch):
    saved = []
    def replay(value):
        if not saved: saved.append(value)
        return saved[0]
    probe, calls = client(monkeypatch, replay)
    probe.verify()
    with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): probe.verify()
    assert len(calls) == 2


@pytest.mark.parametrize("change", ["duck", "no-access", "wrong-root", "tab", "mode"])
def test_trusted_construction_refuses_before_transport(monkeypatch, change):
    probe, calls = client(monkeypatch)
    port, spec, bound, access = probe.transport, SPEC, HANDLE, FolderAccess(BINDING, True, True)
    if change == "duck": port = SyntheticPort()
    if change == "no-access": access = FolderAccess(BINDING, False, True)
    if change == "wrong-root": bound = replace(HANDLE, object_id=DOMAIN)
    if change == "tab": bound = replace(HANDLE, tab_id="synthetic-tab")
    if change == "mode": spec = replace(SPEC, mode="NATIVE_DOCS")
    with pytest.raises(AuthorityError): FolderProbe(port, spec, bound, access)
    assert not calls


@pytest.mark.parametrize("field,value", [("operation", "CAS"), ("path", "SYNTHETIC_PRIVATE_CANARY"),
    ("blueprint", "bad"), ("authority", "bad"), ("mode", "FOLDER_SQLITE_V1"),
    ("root", DOMAIN), ("domain", BINDING.root_id), ("nonce", "invalid")])
def test_invalid_probe_request_never_touches_storage(monkeypatch, field, value):
    config = FolderConfig(Path.cwd() / "synthetic-unused", BINDING, (0, 0), (0, 0), (0, 0))
    calls = []
    monkeypatch.setattr(FolderConfig, "verify", lambda _: calls.append("verify"))
    request = {**probe_header(BINDING, "a" * 32), "operation": "VERIFY",
               "blueprint": SPEC.fingerprint, "authority": HANDLE.seal, field: value}
    raw = handle_probe(config, encoded(request))
    assert flat_json(raw)["result"] == "UNKNOWN" and not calls
    assert b"SYNTHETIC_PRIVATE_CANARY" not in raw and b"body" not in raw


def test_default_read_cas_handler_does_not_accept_probe():
    store = SyntheticPort()
    request = {**probe_header(BINDING, "a" * 32), "operation": "VERIFY",
               "blueprint": SPEC.fingerprint, "authority": HANDLE.seal}
    assert flat_json(handle(store, encoded(request))) == {"result": "UNKNOWN"}
    assert store.commits == 0
