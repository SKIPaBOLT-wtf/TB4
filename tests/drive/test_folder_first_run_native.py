"""Actual Linux helper/SSH physical proof through actual protected first-run."""
from pathlib import Path
import shutil
import sys
import os

import pytest

from tb4.commissioning_checks import CommissionedStorage, detect_environment
from tb4.commissioning_state import Setup, DenyActivation
from tb4.drive.folder_authority import FolderStore, identity
from tb4.drive.folder_first_run import RemoteFolderCommissioning
from tb4.drive.folder_probe import FolderProbe
from tb4.drive.folder_protocol import FolderAccess
from tb4.drive.folder_transport import FixedProcess
from tb4.private_settings import native_settings
from test_folder_commissioning import context
from test_folder_probe_native import prepared, helper_file
from test_folder_ssh import Server
from test_folder_first_run import setup_for

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux remote Folder first-run")


def first_run(parent, probe):
    private = parent / "first-run-private"
    private.mkdir(mode=0o700)
    store = native_settings(private / "profile", create=True, owner_authorized=True)
    model, checker = setup_for(store, CommissionedStorage(RemoteFolderCommissioning(probe)),
        environment=lambda: detect_environment(launch_mode="DESKTOP_SESSION"))
    return model, checker, store


@pytest.mark.parametrize("change", ["missing", "replace", "permission"])
def test_actual_fixed_helper_first_run_detects_later_physical_loss_without_mutation(context, tmp_path, change):
    spec, port, bound, _ = prepared(context)
    config = port._config()
    path = helper_file(tmp_path, config)
    transport = FixedProcess(port.binding, (sys.executable, "-m", "tb4.drive.folder_helper",
        "--config", str(path), "--commissioning-probe"))
    probe = FolderProbe(transport, spec, bound, FolderAccess(port.binding, True, True))
    model, checker, store = first_run(tmp_path, probe)
    before = FolderStore(config).read()
    assert model.review(checker)["settings_validated"]
    saved = store.read().payload
    key = spec.artifact_keys[0]
    payload = port.root / port.prepare(key, spec.operation(key)).object_id
    payload.write_bytes(b"synthetic-used-first-run-payload")
    if change in {"missing", "replace"}:
        payload.rename(port.root / "held-first-run-payload")
        if change == "replace": port.create(key, port.prepare(key, spec.operation(key)))
    else: payload.chmod(0o644)
    objects = {p.name: identity(p) for p in port.root.iterdir()}
    result = Setup(native_settings(store.native.root)).activate(checker, DenyActivation())
    assert result["reason"] == "STORAGE_UNAVAILABLE" and not result["runtime_active"]
    assert FolderStore(config).read() == before
    assert objects == {p.name: identity(p) for p in port.root.iterdir()}
    after = store.read().payload
    for field in ("installation_id", "setup_nonce", "choices", "operations"):
        assert after[field] == saved[field]
    held = port.root / "held-first-run-payload" if change in {"missing", "replace"} else payload
    assert held.read_bytes() == b"synthetic-used-first-run-payload"


def test_actual_isolated_ssh_first_run_requires_new_physical_proof_after_success(context, tmp_path):
    sshd = shutil.which("sshd") or ("/usr/sbin/sshd" if Path("/usr/sbin/sshd").exists() else None)
    ssh = shutil.which("ssh")
    if not sshd or not ssh:
        if os.environ.get("TB4_REQUIRE_FOLDER_SSH") == "1": pytest.fail("Required OpenSSH tools unavailable")
        pytest.skip("Isolated SSH tools required")
    spec, port, bound, _ = prepared(context)
    config = port._config()
    server = Server(tmp_path, helper_file(tmp_path, config), sshd, ssh, probe=True)
    try:
        probe = FolderProbe(server.transport("client-a"), spec, bound, FolderAccess(port.binding, True, True))
        model, checker, store = first_run(tmp_path, probe)
        before = FolderStore(config).read()
        assert model.review(checker)["settings_validated"]
        saved = store.read().payload
        key = spec.artifact_keys[0]
        payload = port.root / port.prepare(key, spec.operation(key)).object_id
        payload.chmod(0o644)
        assert model.review(checker)["reason"] == "STORAGE_UNAVAILABLE"
        assert not model.status()["runtime_active"] and FolderStore(config).read() == before
        assert store.read().payload["choices"] == saved["choices"]
        assert store.read().payload["operations"] == saved["operations"]
    finally: server.stop()
