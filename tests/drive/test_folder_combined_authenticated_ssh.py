"""Actual native dual-purpose credentials through one opt-in forced SSH helper."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import getpass
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

from tb4.credential_contract import Purpose
from tb4.credential_persistence import export_private, restore_private
from tb4.drive.docs_authority import AuthorityError, WriteResult
from tb4.drive.folder_authority import FolderStore, identity
from tb4.drive.folder_authority_transport import CredentialAuthorityProcess, credential_authority_pair
from tb4.drive.folder_first_run import RemoteFolderCommissioning
from tb4.drive.folder_probe import FolderProbe
from tb4.drive.folder_probe_transport import ProbeEndpoint, CredentialProbeProcess, credential_probe_pair
from tb4.drive.folder_protocol import FolderAccess, FolderAuthority, flat_json, header
from tb4.drive.folder_transport import FixedProcess
from tb4.drive.leadership import Leadership
from tb4.exchange_layout import encoded
from tb4.linux_key_native import LinuxKeyNative
from tb4.private_settings import native_settings
from test_folder_commissioning import context
from test_folder_probe_native import prepared, helper_file
from test_folder_ssh import Server
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid

pytestmark = pytest.mark.skipif(sys.platform != "linux",
    reason="Actual Linux native dual-scope credential fixed SSH helper")
TARGET = "00000000-0000-4000-8000-000000000248"
TRUST = "c" * 64
SCOPES = frozenset({Purpose.FOLDER_PROBE, Purpose.FOLDER_AUTHORITY})


@pytest.fixture
def combined(context, tmp_path):
    sshd = shutil.which("sshd") or ("/usr/sbin/sshd" if Path("/usr/sbin/sshd").exists() else None)
    ssh = shutil.which("ssh")
    if not sshd or not ssh:
        if os.environ.get("TB4_REQUIRE_FOLDER_SSH") == "1":
            pytest.fail("Required actual OpenSSH tools unavailable")
        pytest.skip("Optional local SSH tools, required in CI")
    spec, port, bound, _ = prepared(context)
    config = port._config()
    directory = tmp_path / "synthetic-combined-ssh"
    directory.mkdir(mode=0o700)
    server = Server(directory, helper_file(tmp_path, config), sshd, ssh, dispatch=True)
    try:
        known = directory / "known"
        known.chmod(0o600)
        native = LinuxKeyNative()
        with native.open_key(str(known), native.identity().uid) as held:
            version = held.version
        endpoint = ProbeEndpoint(TARGET, TRUST, str(Path(ssh).resolve()), "127.0.0.1",
                                 server.port, getpass.getuser(), str(known), version)
        now = [100]
        def pair(installation):
            return credential_authority_pair(installation, endpoint, port.binding, clock=lambda: now[0])
        def make(name, installation):
            store, resolver = pair(installation)
            key = directory / name
            reference = store.select(path=str(key), target_id=TARGET, target_trust=TRUST,
                purposes=SCOPES, expires_at=200, access_mode="existing_key",
                launch_mode="headless", owner_authorized=True)
            handle = resolver.enroll(target_id=TARGET, target_trust=TRUST, store_locator=reference,
                purposes=SCOPES, expires_at=200, owner_authorized=True)
            return SimpleNamespace(store=store, resolver=resolver, key=key, reference=reference,
                handle=handle, installation=installation)
        def connect(selected, image=None):
            image = export_private(selected.store, selected.resolver) if image is None else image
            authority_store, authority_resolver = pair(selected.installation)
            restore_private(image, authority_store, authority_resolver)
            probe_store, probe_resolver = credential_probe_pair(selected.installation, endpoint, spec,
                                                               bound, clock=lambda: now[0])
            restore_private(image, probe_store, probe_resolver)
            process = CredentialAuthorityProcess(authority_resolver, selected.handle)
            probe_process = CredentialProbeProcess(probe_resolver, selected.handle)
            access = FolderAccess(port.binding, True, True)
            return SimpleNamespace(store=authority_store, resolver=authority_resolver, process=process,
                client=FolderAuthority(process, port.binding, access),
                probe_store=probe_store, probe_resolver=probe_resolver, probe_process=probe_process,
                probe=FolderProbe(probe_process, spec, bound, access))
        a, b = make("client-a", ACTORS[0]), make("client-b", ACTORS[1])
        image = export_private(a.store, a.resolver)
        profile = native_settings(tmp_path / "synthetic-combined-profile", create=True, owner_authorized=True)
        profile.save({"registry": image, "history": {"inherited": "UNKNOWN"}}, expected_revision=0)
        yield SimpleNamespace(a=a, b=b, connect=connect, pair=pair, config=config, spec=spec,
            bound=bound, port=port, server=server, endpoint=endpoint, now=now, known=known,
            image=image, profile=profile)
    finally:
        server.stop()


def objects(value):
    return {p.name: identity(p) for p in value.config.root.iterdir()}


def desired(snapshot):
    value = snapshot.document()
    value["records"]["global.summary"].update(retention="BUSY", body={"synthetic-combined": True})
    return value


def test_same_protected_image_restarts_probe_read_cas_and_preserves_key_history_and_files(combined, monkeypatch, capsys):
    v = combined
    saved, inventory = v.profile.read(), objects(v)
    key_bytes = v.a.key.read_bytes()
    native = native_settings(Path(v.profile.native.root))
    selected = v.connect(v.a, native.read().payload["registry"])
    original, commands = FixedProcess.call, []
    def observe(transport, raw):
        commands.append(transport.argv[-1])
        assert transport.argv[-1] in {"tb4-folder-v1", "tb4-folder-probe-v1"}
        for prefix in ("-oIdentityFile=", "-oUserKnownHostsFile="):
            argument = next(x for x in transport.argv if x.startswith(prefix))
            assert f"/proc/{os.getpid()}/fd/" in argument
            assert str(v.a.key) not in argument and str(v.known) not in argument
        return original(transport, raw)
    monkeypatch.setattr(FixedProcess, "call", observe)
    before = FolderStore(v.config).read()
    proof = selected.probe.verify()
    assert RemoteFolderCommissioning(selected.probe).verify(
        dict(spec=asdict(v.spec), authority=v.bound.record())) == proof.document()
    assert FolderStore(v.config).read() == before and proof.revision == before[0]
    snapshot = selected.client.read()
    value = desired(snapshot)
    assert selected.client.compare_replace(snapshot, value) is WriteResult.ACCEPTED
    assert selected.client.read().document() == value
    assert selected.probe.verify().document() == value
    assert commands.count("tb4-folder-probe-v1") == 3 and commands.count("tb4-folder-v1") == 3
    assert export_private(selected.store, selected.resolver) == v.image
    assert export_private(selected.probe_store, selected.probe_resolver) == v.image
    assert native.read() == saved and objects(v) == inventory and v.a.key.read_bytes() == key_bytes
    assert key_bytes not in (Path(v.profile.native.root) / "settings.json").read_bytes()
    assert selected.process._runner._pending is selected.probe_process._runner._pending is None
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("command", ["", "tb4-folder-v1 extra", "tb4-folder-v1;synthetic-command",
                                     "tb4-folder-probe-v1 extra"])
def test_real_forced_helper_refuses_unknown_command_without_mutating_storage(combined, monkeypatch, command):
    v = combined
    saved, before, inventory = v.profile.read(), FolderStore(v.config).read(), objects(v)
    transport = v.server.transport("client-a")
    raw = encoded({**header(v.port.binding, "a" * 32), "operation": "READ"})
    original, calls = FixedProcess.call, []
    def observe(actual, request):
        calls.append(actual.argv[-1])
        return original(actual, request)
    monkeypatch.setattr(FixedProcess, "call", observe)
    # Empty argv is refused by the existing client constructor before SSH.
    # Nonempty invalid tokens reach the actual forced helper once.
    code = "HELPER_COMMAND" if command == "" else "HELPER_UNAVAILABLE"
    with pytest.raises(AuthorityError, match="^" + code + "$"):
        transport = replace(transport, argv=(*transport.argv[:-1], command))
        transport.call(raw)
    assert calls == ([] if command == "" else [command])
    assert FolderStore(v.config).read() == before and objects(v) == inventory and v.profile.read() == saved


@pytest.mark.parametrize("operation", ["VERIFY_AS_NORMAL", "READ_AS_PROBE", "CAS_AS_PROBE"])
def test_command_and_payload_confusion_never_mutates_or_proves_storage(combined, monkeypatch, operation):
    v = combined
    selected = v.connect(v.a)
    saved, before, inventory = v.profile.read(), FolderStore(v.config).read(), objects(v)
    original = FixedProcess.call
    snapshot = selected.client.read()
    def swap(transport, raw):
        command = "tb4-folder-v1" if operation == "VERIFY_AS_NORMAL" else "tb4-folder-probe-v1"
        return original(replace(transport, argv=(*transport.argv[:-1], command)), raw)
    monkeypatch.setattr(FixedProcess, "call", swap)
    if operation == "VERIFY_AS_NORMAL":
        with pytest.raises(AuthorityError):
            selected.probe.verify()
    elif operation == "READ_AS_PROBE":
        with pytest.raises(AuthorityError):
            selected.client.read()
    else:
        assert selected.client.compare_replace(snapshot, desired(snapshot)) is WriteResult.UNKNOWN
    assert FolderStore(v.config).read() == before and objects(v) == inventory and v.profile.read() == saved
    assert selected.process._runner._pending is selected.probe_process._runner._pending is None


def test_actual_combined_two_native_clients_have_one_cas_winner(combined):
    v = combined
    a, b = v.connect(v.a), v.connect(v.b)
    saved, inventory = v.profile.read(), objects(v)
    a.probe.verify(); b.probe.verify()
    old = [a.client.read(), b.client.read()]
    value = desired(old[0])
    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(lambda n: (a.client, b.client)[n].compare_replace(old[n], value), range(2)))
    assert result.count(WriteResult.ACCEPTED) == 1
    assert set(result) <= {WriteResult.ACCEPTED, WriteResult.REJECTED, WriteResult.UNAVAILABLE}
    assert a.client.read().document() == b.client.read().document() == value
    assert b.client.compare_replace(old[1], value) is WriteResult.REJECTED
    assert objects(v) == inventory and v.profile.read() == saved


def test_combined_helper_lost_commit_reply_remains_unknown_and_read_or_probe_never_resends(combined, monkeypatch):
    v = combined
    selected = v.connect(v.a)
    before = selected.client.read()
    value = desired(before)
    saved, inventory = v.profile.read(), objects(v)
    original, writes = FixedProcess.call, []
    def lost(transport, raw):
        reply = original(transport, raw)
        if transport.argv[-1] == "tb4-folder-v1" and flat_json(raw)["operation"] == "CAS":
            writes.append(raw)
            raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
        return reply
    monkeypatch.setattr(FixedProcess, "call", lost)
    assert selected.client.compare_replace(before, value) is WriteResult.UNKNOWN and len(writes) == 1
    assert selected.client.read().document() == selected.probe.verify().document() == value
    assert len(writes) == 1 and FolderStore(v.config).read()[0] == before.revision + 1
    assert v.profile.read() == saved and objects(v) == inventory


def test_combined_helper_stale_and_forced_first_cas_takeover_preserve_unknown_without_peer_ack(combined):
    v = combined
    a, b = v.connect(v.a), v.connect(v.b)
    saved = v.profile.read()
    old = a.client.read()
    value = old.document()
    value["records"]["target.000.work"].update(generation=7, operation_id="old-unknown",
        retention="BUSY", body={"unknown": True})
    assert a.client.compare_replace(old, value) is WriteResult.ACCEPTED
    preserved = a.client.read().document()["records"]["target.000.work"]
    x, y = (Leadership(port, actor=actor, enrollment=ENROLLMENT)
            for port, actor in ((a.client, ACTORS[0]), (b.client, ACTORS[1])))
    # The ready-marker fixture already has an initial leader. Read-only physical
    # proof does not wait for it; the first stale conditional claimant succeeds.
    plan = y.acquire(y.observe(clock(220)), transition=tid("combined-stale"))
    new = y.confirmed_grant(plan, y.commit(plan, mode="START"))
    assert new.epoch == 2
    request = x.request_force(x.observe(clock(221)), request_id=tid("combined-force"), user_requested=True)
    assert x.commit(request, mode="START").outcome == "CONFIRMED"
    assert not y.current_before_dispatch(new, clock(221))
    claim = x.claim_requested(x.observe(clock(221)), request_id=tid("combined-force"))
    newest = x.confirmed_grant(claim, x.commit(claim, mode="START"))
    assert newest.epoch == 3
    assert a.client.read().document()["records"]["target.000.work"] == preserved
    assert v.profile.read() == saved


@pytest.mark.parametrize("change", ["key-version", "key-permission", "known-version",
                                   "known-permission", "expired", "revoked"])
def test_combined_prior_proof_does_not_authorize_later_credential_loss(combined, monkeypatch, change):
    v = combined
    selected = v.connect(v.a)
    selected.probe.verify()
    snapshot = selected.client.read()
    saved, before, inventory = v.profile.read(), FolderStore(v.config).read(), objects(v)
    if change == "key-version": v.a.key.write_bytes(b"synthetic-later-key")
    if change == "key-permission": v.a.key.chmod(0o644)
    if change == "known-version": v.known.write_bytes(b"synthetic-later-known")
    if change == "known-permission": v.known.chmod(0o644)
    if change == "expired": v.now[0] = 200
    if change == "revoked":
        selected.resolver.revoke(v.a.handle, owner_authorized=True)
        selected.probe_resolver.revoke(v.a.handle, owner_authorized=True)
    def forbidden(*_):
        pytest.fail("Lost credential reached fixed process")
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    with pytest.raises(AuthorityError):
        selected.probe.verify()
    assert selected.client.compare_replace(snapshot, desired(snapshot)) is WriteResult.UNKNOWN
    assert FolderStore(v.config).read() == before and objects(v) == inventory and v.profile.read() == saved
    assert selected.process._runner._pending is selected.probe_process._runner._pending is None

