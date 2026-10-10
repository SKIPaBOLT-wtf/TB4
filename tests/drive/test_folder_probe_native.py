"""Actual owned Linux files, lock ordering and isolated forced-command SSH."""
import base64
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

from tb4.drive.commissioning_folder import ATTR
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import DB, FolderStore, identity
from tb4.drive.folder_helper import load_config
from tb4.drive.folder_probe import FolderProbe, handle_probe, probe_header
from tb4.drive.folder_protocol import FolderAccess, flat_json
from tb4.exchange_layout import encoded
from test_fixed_slot_commissioning import finish
from test_folder_commissioning import context, initialized
from test_folder_ssh import Server

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux physical Folder probe")


def prepared(context):
    spec, port, _ = context
    _, bound, commissioner = initialized(context)
    finish(commissioner)
    request = {**probe_header(port.binding, "a" * 32), "operation": "VERIFY",
               "blueprint": spec.fingerprint, "authority": bound.seal}
    return spec, port, bound, request


def test_actual_physical_proof_preserves_revision_payload_and_objects(context, monkeypatch):
    spec, port, bound, request = prepared(context)
    key = spec.artifact_keys[0]
    payload = port.root / port.prepare(key, spec.operation(key)).object_id
    payload.write_bytes(b"synthetic-used-payload")
    config = port._config(); before = FolderStore(config).read()
    objects = {p.name: identity(p) for p in port.root.iterdir()}
    monkeypatch.setattr(FolderStore, "compare_replace", lambda *_: pytest.fail("Probe attempted CAS"))
    response = flat_json(handle_probe(config, encoded(request)))
    assert response["result"] == "VERIFIED" and response["revision"] == before[0]
    assert base64.b64decode(response["body"]) == before[1]
    assert FolderStore(config).read() == before
    assert objects == {p.name: identity(p) for p in port.root.iterdir()}
    assert payload.read_bytes() == b"synthetic-used-payload"
    assert response["authority"] == bound.seal


@pytest.mark.parametrize("change", ["missing", "replace", "marker", "permission", "alias",
                                     "authority-marker", "authority-handle", "blueprint"])
def test_actual_probe_refuses_physical_or_expected_identity_loss(context, change):
    spec, port, _, request = prepared(context)
    config = port._config()
    key = spec.artifact_keys[0]; allocation = port.prepare(key, spec.operation(key))
    path = port.root / allocation.object_id
    if change == "missing": path.rename(port.root / "held-synthetic")
    if change == "replace":
        path.rename(port.root / "held-synthetic"); port.create(key, allocation)
    if change == "marker": os.setxattr(path, ATTR, b"SYNTHETIC_PRIVATE_CANARY")
    if change == "permission": path.chmod(0o644)
    if change == "alias": os.link(path, port.root / "alias-synthetic")
    if change == "authority-marker": os.setxattr(port.root / DB, ATTR, b"SYNTHETIC_PRIVATE_CANARY")
    if change == "authority-handle": request["authority"] = "b" * 64
    if change == "blueprint": request["blueprint"] = "b" * 64
    before = FolderStore(config).read()
    raw = handle_probe(config, encoded(request))
    assert flat_json(raw)["result"] == "UNKNOWN" and b"body" not in raw
    assert b"SYNTHETIC_PRIVATE_CANARY" not in raw and FolderStore(config).read() == before


def test_actual_incomplete_commissioning_is_not_a_physical_proof(context):
    spec, port, _ = context
    _, bound, _ = initialized(context)
    request = {**probe_header(port.binding, "a" * 32), "operation": "VERIFY",
               "blueprint": spec.fingerprint, "authority": bound.seal}
    assert flat_json(handle_probe(port._config(), encoded(request)))["result"] == "UNKNOWN"


def test_actual_probe_has_no_nested_database_lock(context, monkeypatch):
    from contextlib import contextmanager
    _, port, _, request = prepared(context)
    original = FolderStore.connection
    depth = 0; calls = []
    @contextmanager
    def guarded(self):
        nonlocal depth
        assert depth == 0, "Nested physical proof database lock"
        with original(self) as connection:
            depth += 1; calls.append("lock")
            try: yield connection
            finally: depth -= 1
    monkeypatch.setattr(FolderStore, "connection", guarded)
    assert flat_json(handle_probe(port._config(), encoded(request)))["result"] == "VERIFIED"
    assert len(calls) == 3 and depth == 0


def helper_file(parent, config):
    value = dict(version=1, root=config.binding.root_id, domain=config.binding.domain_id,
        path=str(config.root), root_dev=config.root_identity[0], root_ino=config.root_identity[1],
        db_dev=config.db_identity[0], db_ino=config.db_identity[1],
        journal_dev=config.journal_identity[0], journal_ino=config.journal_identity[1])
    path = parent / "synthetic-probe-helper.json"
    path.write_text(json.dumps(value), encoding="utf-8"); path.chmod(0o600)
    assert load_config(path) == config
    return path


@pytest.mark.parametrize("probe_enabled", [False, True])
def test_actual_fixed_ssh_command_requires_explicit_probe_and_fresh_physical_access(context, tmp_path, probe_enabled):
    sshd = shutil.which("sshd") or ("/usr/sbin/sshd" if Path("/usr/sbin/sshd").exists() else None)
    ssh = shutil.which("ssh")
    if not sshd or not ssh:
        if os.environ.get("TB4_REQUIRE_FOLDER_SSH") == "1": pytest.fail("Required OpenSSH tools unavailable")
        pytest.skip("Isolated SSH tools required")
    spec, port, bound, _ = prepared(context)
    config = port._config(); before = FolderStore(config).read()
    server = Server(tmp_path, helper_file(tmp_path, config), sshd, ssh, probe=probe_enabled)
    try:
        probe = FolderProbe(server.transport("client-a"), spec, bound,
                            FolderAccess(port.binding, True, True))
        if not probe_enabled:
            with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): probe.verify()
        else:
            proof = probe.verify()
            assert (proof.revision, proof.raw) == before
            key = spec.artifact_keys[0]
            path = port.root / port.prepare(key, spec.operation(key)).object_id
            path.chmod(0o644)
            with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): probe.verify()
        assert FolderStore(config).read() == before
    finally: server.stop()
