"""Actual native C1/Candidate review through mapped fixed loopback SSH."""
from dataclasses import asdict
import getpass
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

from tb4.commissioning_checks import Prerequisites, detect_environment
from tb4.commissioning_state import Setup, DenyActivation
from tb4.configuration_contract import ConfigurationError
from tb4.credential_contract import Purpose
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import DB, JOURNAL, FolderStore, identity
from tb4.drive.folder_authority_transport import credential_authority_pair
from tb4.drive.folder_connection import NativeFolderConnection
from tb4.drive.folder_endpoint import NativeFolderEndpoint
from tb4.drive.folder_endpoint_attachment import NativeFolderEndpointAttachment
from tb4.drive.folder_helper import load_config
from tb4.drive.folder_prerequisites import native_folder_prerequisites
from tb4.drive.folder_probe_transport import ProbeEndpoint
from tb4.drive.folder_protocol import FolderAccess
from tb4.drive.folder_transport import FixedProcess
from tb4.linux_key_native import LinuxKeyNative
from tb4.private_settings import native_settings, SettingsError
from tb4.reconfiguration_candidate import Candidate
from tests.drive.folder_retained_support import system
from test_folder_commissioning import context
from test_folder_ssh import Server

pytestmark = pytest.mark.skipif(sys.platform != "linux",
    reason="Actual native staged Candidate and protected mapped SSH helper")
TARGET = "00000000-0000-4000-8000-000000000251"
TRUST = "d" * 64
SCOPES = frozenset({Purpose.FOLDER_PROBE, Purpose.FOLDER_AUTHORITY})


@pytest.fixture
def staged(context, tmp_path, request):
    sshd = shutil.which("sshd") or ("/usr/sbin/sshd" if Path("/usr/sbin/sshd").exists() else None)
    ssh = shutil.which("ssh")
    if not sshd or not ssh:
        if os.environ.get("TB4_REQUIRE_FOLDER_SSH") == "1":
            pytest.fail("Required actual OpenSSH tools unavailable")
        pytest.skip("Optional local SSH tools, required in CI")
    moved = getattr(request, "param", True)
    s = system(context, tmp_path, moved=moved)
    port = s.ctx.storage_port
    expected, current = port.expected, port._config()
    directory = tmp_path / "owned-candidate-ssh"
    directory.mkdir(mode=0o700)
    helper = directory / "helper.json"
    helper.write_text(json.dumps(dict(version=1, root=expected.binding.root_id,
        domain=expected.binding.domain_id, path=str(expected.root),
        root_dev=expected.root_identity[0], root_ino=expected.root_identity[1],
        db_dev=expected.db_identity[0], db_ino=expected.db_identity[1],
        journal_dev=expected.journal_identity[0], journal_ino=expected.journal_identity[1])),
        encoding="utf-8")
    helper.chmod(0o600)
    mapping = Path(port.mapping.store.native.root)
    assert load_config(helper, mapping_store=mapping) == current
    server = Server(directory, helper, sshd, ssh, dispatch=True, mapping_store=mapping)
    try:
        known = directory / "known"
        known.chmod(0o600)
        native = LinuxKeyNative()
        with native.open_key(str(known), native.identity().uid) as held:
            version = held.version
        endpoint = ProbeEndpoint(TARGET, TRUST, str(Path(ssh).resolve()), "127.0.0.1",
            server.port, getpass.getuser(), str(known), version)
        profile = s.candidate.context.profile
        model = Setup(profile)
        now = [220]
        store, resolver = credential_authority_pair(model.installation_id, endpoint,
            port.binding, clock=lambda:now[0])
        key = directory / "client-a"
        reference = store.select(path=str(key), target_id=TARGET, target_trust=TRUST,
            purposes=SCOPES, expires_at=1000, access_mode="existing_key",
            launch_mode="headless", owner_authorized=True)
        handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=reference,
            purposes=SCOPES, expires_at=1000, owner_authorized=True)
        model.persist_credentials(store, resolver, [dict(handle=handle, target_id=TARGET,
            target_trust=TRUST, purposes=sorted(p.value for p in SCOPES))])
        metadata = native_settings(tmp_path / "candidate-endpoint", create=True, owner_authorized=True)
        selected = NativeFolderEndpoint(metadata, model.installation_id)
        selected_ref = selected.prepare(model, endpoint, handle, owner_authorized=True)
        NativeFolderEndpointAttachment(selected, profile).attach(model, selected_ref, owner_authorized=True)
        access = FolderAccess(port.binding, True, True)
        checker = native_folder_prerequisites(profile, access=access,
            environment=lambda:detect_environment(launch_mode="EXTERNAL"),
            source=s.ctx.source, runtime=s.ctx.runtime, clock=lambda:now[0])
        yield SimpleNamespace(s=s, port=port, current=current, profile=profile, model=model,
            metadata=metadata, endpoint=endpoint, access=access, checker=checker,
            store=store, resolver=resolver, handle=handle, key=key, known=known, now=now,
            server=server, mapping=mapping)
    finally:
        server.stop()


def retained(v):
    root = v.current.root
    return (v.s.ctx.setup.store.read(), v.s.candidate.context.archive.read(),
        v.metadata.read(), FolderStore(v.current).read(),
        {p.name:identity(p) for p in root.iterdir()},
        {p.name:p.read_bytes() for p in root.iterdir() if p.name not in {DB, JOURNAL}})


@pytest.mark.parametrize("staged", [False, True], indirect=True)
def test_actual_candidate_review_restart_uses_mapped_ssh_and_retains_main_work(staged, monkeypatch, capsys):
    v = staged
    before, previous = retained(v), v.profile.read()
    calls, original = [], FixedProcess.call
    def observe(process, raw):
        calls.append(process.argv[-1])
        return original(process, raw)
    def forbidden(*_args, **_kwargs): pytest.fail("Candidate review selected credentials or sent shared CAS")
    monkeypatch.setattr(FixedProcess, "call", observe)
    monkeypatch.setattr(v.store.__class__, "select", forbidden)
    monkeypatch.setattr(v.resolver.__class__, "enroll", forbidden)
    monkeypatch.setattr(FolderStore, "compare_replace", forbidden)
    assert type(v.checker) is Prerequisites
    assert v.s.candidate.review(v.checker)["settings_validated"]
    assert calls == ["tb4-folder-probe-v1"]
    assert v.profile.read().previous == previous.payload
    restarted = Candidate(v.s.candidate.context)
    assert not restarted.view()["settings_validated"]
    checked = restarted.require_validated(v.checker)
    assert checked.revision == v.profile.read().revision
    assert calls == ["tb4-folder-probe-v1"] * 3
    current = NativeFolderConnection(v.profile, clock=lambda:v.now[0])
    assert current.authority_client(v.access).read().document() == v.s.ctx.leadership.backend.read().document()
    assert calls[-1] == "tb4-folder-v1"
    assert retained(v) == before
    assert v.profile.read().payload["installation_id"] == before[0].payload["installation_id"]
    assert v.profile.read().payload["setup_nonce"] == before[0].payload["setup_nonce"]
    assert v.profile.read().payload["operations"] == before[0].payload["operations"]
    assert v.port.mapping.select(v.port.expected) == v.current
    assert not restarted.view()["runtime_active"]
    setup = Setup(v.profile)
    assert setup.activate(v.checker, DenyActivation())["reason"] == "ACTIVATION_NOT_AUTHORIZED"
    assert retained(v) == before
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("change", ["unselected", "revoked", "selection-revoked",
    "key-version", "known-version", "key-permission", "expired"])
def test_actual_ready_candidate_never_hides_current_loss_or_reaches_ssh(staged, monkeypatch, change):
    v = staged
    assert v.s.candidate.review(v.checker)["settings_validated"]
    before = retained(v)
    current = v.profile.read(); payload = current.payload
    if change == "unselected": payload["choices"]["credentials"] = []
    if change == "revoked": payload["credential_image"]["bindings"][v.handle]["revoked"] = True
    if change == "selection-revoked":
        for row in payload["credential_image"]["selections"].values(): row["revoked"] = True
    if change in {"unselected", "revoked", "selection-revoked"}:
        v.profile.save(payload, expected_revision=current.revision)
    if change == "key-version": v.key.write_bytes(b"synthetic-replaced-key")
    if change == "known-version": v.known.write_bytes(b"synthetic-replaced-known")
    if change == "key-permission": v.key.chmod(0o644)
    if change == "expired": v.now[0] = 1001
    def forbidden(*_args, **_kwargs): pytest.fail("Failed current candidate reached SSH")
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    report = Candidate(v.s.candidate.context).review(v.checker)
    assert not report["settings_validated"] and not report["runtime_active"]
    assert v.profile.read().payload["reason"] in {"STORAGE_UNAVAILABLE", "MISSING_CHOICES"}
    assert v.checker.credentials is None
    assert retained(v) == before


@pytest.mark.parametrize("which", ["profile", "endpoint"])
def test_actual_staged_native_pending_is_preserved_without_ssh_or_recovery(staged, monkeypatch, which):
    v = staged
    before, profile = retained(v), v.profile.read()
    store = v.profile if which == "profile" else v.metadata
    with store.native.locked() as port:
        raw = port.read("settings.json")
        port.stage(raw)
    def forbidden(*_args, **_kwargs): pytest.fail("Pending candidate reached SSH")
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"):
        v.checker.validate(profile.payload)
    with store.native.locked() as port:
        assert port.read("settings.json") == raw and port.read("settings.pending") == raw
    assert v.checker.credentials is None
    if which == "profile":
        assert v.s.ctx.setup.store.read() == before[0]
        assert v.s.candidate.context.archive.read() == before[1]
        assert v.metadata.read() == before[2]
    else:
        assert v.profile.read() == profile
        assert v.s.ctx.setup.store.read() == before[0]
    assert FolderStore(v.current).read() == before[3]


@pytest.mark.parametrize("fault", ["missing-artifact", "conflicting-source"])
def test_actual_mapped_physical_loss_cannot_validate_candidate_or_change_main(staged, fault, monkeypatch):
    v = staged
    assert v.s.candidate.review(v.checker)["settings_validated"]
    main, archive = v.s.ctx.setup.store.read(), v.s.candidate.context.archive.read()
    profile = v.profile.read()
    shared = FolderStore(v.current).read()
    if fault == "missing-artifact":
        key = v.port.spec.artifact_keys[0]
        path = v.current.root / v.port.base.prepare(key, v.port.spec.operation(key)).object_id
        path.rename(v.current.root / "held-synthetic-artifact")
    else:
        assert not v.port.expected.root.exists()
        v.port.expected.root.mkdir(mode=0o700)
    def forbidden(*_args, **_kwargs): pytest.fail("Early C1 refusal reached SSH")
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    code = "CONFIGURATION_CONTEXT_UNAVAILABLE" if fault == "missing-artifact" else "FOLDER_MAPPING_CONFLICT"
    with pytest.raises(ConfigurationError, match="^" + code + "$"):
        v.s.candidate.review(v.checker)
    view = v.s.candidate.view()
    assert not view["settings_validated"] and not view["runtime_active"]
    assert v.profile.read() == profile
    assert v.s.ctx.setup.store.read() == main and v.s.candidate.context.archive.read() == archive
    assert FolderStore(v.current).read() == shared
