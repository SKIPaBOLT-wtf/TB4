"""Actual protected Setup restart through the isolated fixed SSH helper."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import sys
from types import SimpleNamespace

import pytest

from tb4.commissioning_checks import CommissionedStorage
from tb4.commissioning_state import Setup, validated
from tb4.credential_contract import CredentialResolver, Purpose
from tb4.drive.docs_authority import AuthorityError, WriteResult
from tb4.drive.folder_connection import NativeFolderConnection
from tb4.drive.folder_endpoint import NativeFolderEndpoint
from tb4.drive.folder_endpoint_attachment import NativeFolderEndpointAttachment
from tb4.drive.folder_first_run import RemoteFolderCommissioning
from tb4.drive.folder_protocol import FolderAccess, flat_json
from tb4.drive.folder_transport import FixedProcess
from tb4.drive.leadership import Leadership
from tb4.private_settings import native_settings
from tb4.timing_contract import TimingProfile
from test_folder_combined_authenticated_ssh import combined, objects, desired
from test_folder_commissioning import context
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid

pytestmark = pytest.mark.skipif(sys.platform != "linux",
    reason="Actual Linux protected Setup fixed SSH connection")


def connect(v, selected, root):
    profile = native_settings(root, create=True, owner_authorized=True)
    # Existing selected native image, same installation/handle/scope/version.
    from tb4.credential_persistence import export_private
    image = export_private(selected.store, selected.resolver)
    payload = dict(schema_version=1, installation_id=selected.installation,
        setup_nonce="9"*64, state="INCOMPLETE", reason="REVALIDATION_REQUIRED",
        choices=dict(role="watchdog", storage=dict(spec=asdict(v.spec), authority=v.bound.record()),
            storage_request=None, network_scope=[], credentials=[dict(handle=selected.handle,
                target_id=v.endpoint.target_id, target_trust=v.endpoint.trust,
                purposes=[Purpose.FOLDER_PROBE.value, Purpose.FOLDER_AUTHORITY.value])],
            descriptor=None, timing=asdict(TimingProfile())), operations={}, credential_image=image)
    profile.save(validated(payload), expected_revision=0)
    setup = Setup(profile)
    metadata = native_settings(root.parent/(root.name+"-endpoint"), create=True, owner_authorized=True)
    selected_endpoint = NativeFolderEndpoint(metadata, selected.installation)
    reference = selected_endpoint.prepare(setup, v.endpoint, selected.handle, owner_authorized=True)
    NativeFolderEndpointAttachment(selected_endpoint, profile).attach(setup, reference, owner_authorized=True)
    connection = NativeFolderConnection(native_settings(root), clock=lambda:v.now[0])
    access = FolderAccess(v.port.binding, True, True)
    return SimpleNamespace(root=root, profile=profile, setup=setup, metadata=metadata,
        reference=reference, connection=connection, access=access,
        probe=connection.probe(access), client=connection.authority_client(access))


def test_real_protected_setup_restart_first_run_probe_read_cas_and_readback(combined, tmp_path, monkeypatch):
    v = combined
    linked = connect(v, v.a, tmp_path/"owned-setup-a")
    saved, metadata, inventory = linked.profile.read(), linked.metadata.read(), objects(v)
    key_bytes = v.a.key.read_bytes()
    def forbidden(*_args, **_kwargs): pytest.fail("Fresh connection selected, enrolled or rewrote metadata")
    monkeypatch.setattr(v.a.store.__class__, "select", forbidden)
    monkeypatch.setattr(CredentialResolver, "enroll", forbidden)
    monkeypatch.setattr(linked.profile.__class__, "_save_locked", forbidden)
    restarted = NativeFolderConnection(native_settings(linked.root), clock=lambda:v.now[0])
    probe, client = restarted.probe(linked.access), restarted.authority_client(linked.access)
    first = probe.verify()
    storage = linked.setup.private_choices()["storage"]
    assert CommissionedStorage(RemoteFolderCommissioning(probe)).verify(storage) == first.document()
    snapshot = client.read(); value = desired(snapshot)
    assert client.compare_replace(snapshot, value) is WriteResult.ACCEPTED
    assert client.read().document() == probe.verify().document() == value
    assert linked.profile.read() == saved and linked.metadata.read() == metadata
    assert objects(v) == inventory and v.a.key.read_bytes() == key_bytes and v.profile.read().payload["registry"] == v.image


def test_real_two_protected_setup_clients_have_one_cas_winner(combined, tmp_path):
    v = combined
    a, b = connect(v, v.a, tmp_path/"owned-setup-a"), connect(v, v.b, tmp_path/"owned-setup-b")
    saved = a.profile.read(), b.profile.read(), objects(v)
    snapshots = a.client.read(), b.client.read(); value = desired(snapshots[0])
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda i:(a, b)[i].client.compare_replace(snapshots[i], value), range(2)))
    assert results.count(WriteResult.ACCEPTED) == 1
    assert set(results) <= {WriteResult.ACCEPTED, WriteResult.REJECTED, WriteResult.UNAVAILABLE}
    assert a.client.read().document() == b.client.read().document() == value
    assert (a.profile.read(), b.profile.read(), objects(v)) == saved


@pytest.mark.parametrize("change", ["revoked", "unselected", "expired", "key-version", "known-version", "key-permission"])
def test_real_current_selection_or_native_loss_refuses_both_uses_before_ssh(combined, tmp_path, monkeypatch, change):
    v = combined; linked = connect(v, v.a, tmp_path/"owned-setup-a")
    assert linked.probe.verify() and linked.client.read()
    if change in {"revoked", "unselected"}:
        current = linked.profile.read(); payload = current.payload
        if change == "revoked": payload["credential_image"]["bindings"][v.a.handle]["revoked"] = True
        else: payload["choices"]["credentials"] = []
        linked.profile.save(validated(payload), expected_revision=current.revision)
    if change == "expired": v.now[0] = 200
    if change == "key-version": v.a.key.write_bytes(b"synthetic-replaced-key")
    if change == "known-version": v.known.write_bytes(b"synthetic-replaced-known")
    if change == "key-permission": v.a.key.chmod(0o644)
    saved, inventory = linked.profile.read(), objects(v)
    def forbidden(*_args, **_kwargs): pytest.fail("Current refusal reached SSH")
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): linked.probe.verify()
    with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): linked.client.read()
    assert linked.profile.read() == saved and objects(v) == inventory


def first_run_checker(v, linked):
    from tb4.commissioning_checks import detect_environment
    from tb4.drive.folder_prerequisites import native_folder_prerequisites
    from tests.security.test_ballpark_contract import fixture as descriptor
    from tests.security.test_first_run import Source, FACTS
    current = linked.profile.read(); payload = current.payload
    local = descriptor()
    local.update(installation_id=payload["installation_id"], domain_id=v.spec.domain_id)
    payload["choices"]["descriptor"] = local
    linked.profile.save(validated(payload), expected_revision=current.revision)
    linked.setup = Setup(native_settings(linked.root))
    return native_folder_prerequisites(native_settings(linked.root), access=linked.access,
        environment=lambda:detect_environment(launch_mode="EXTERNAL"),
        source=Source(), runtime=FACTS, clock=lambda:v.now[0])


def test_real_native_prerequisites_setup_restart_and_default_activation_are_fresh(combined, tmp_path, monkeypatch):
    from tb4.commissioning_checks import Prerequisites
    from tb4.commissioning_state import DenyActivation
    v = combined; linked = connect(v, v.a, tmp_path/"owned-prerequisite-setup")
    checker = first_run_checker(v, linked)
    before, metadata, inventory, registry = linked.profile.read(), linked.metadata.read(), objects(v), v.profile.read()
    original, calls = FixedProcess.call, []
    def observe(transport, raw):
        calls.append(transport.argv[-1])
        return original(transport, raw)
    monkeypatch.setattr(FixedProcess, "call", observe)
    def forbidden(*_args, **_kwargs): pytest.fail("First-run selected or enrolled a key")
    monkeypatch.setattr(v.a.store.__class__, "select", forbidden)
    monkeypatch.setattr(CredentialResolver, "enroll", forbidden)
    assert type(checker) is Prerequisites and linked.setup.review(checker)["settings_validated"]
    ready = linked.profile.read()
    assert ready.previous == before.payload and calls == ["tb4-folder-probe-v1"]
    assert {k:x for k,x in ready.payload.items() if k not in {"state","reason"}} == {
        k:x for k,x in before.payload.items() if k not in {"state","reason"}}
    restarted = Setup(native_settings(linked.root))
    assert not restarted.status()["settings_validated"] and restarted.review(checker)["settings_validated"]
    assert restarted.activate(checker, DenyActivation())["reason"] == "ACTIVATION_NOT_AUTHORIZED"
    assert linked.metadata.read() == metadata and objects(v) == inventory and v.profile.read() == registry
    assert linked.profile.read().payload["credential_image"] == before.payload["credential_image"]


def test_real_native_prerequisites_current_revocation_refuses_before_ssh(combined, tmp_path, monkeypatch):
    v = combined; linked = connect(v, v.a, tmp_path/"owned-prerequisite-setup")
    checker = first_run_checker(v, linked)
    assert linked.setup.review(checker)["settings_validated"]
    current = linked.profile.read(); payload = current.payload
    payload["credential_image"]["bindings"][v.a.handle]["revoked"] = True
    linked.profile.save(validated(payload), expected_revision=current.revision)
    before, inventory = linked.profile.read(), objects(v)
    def forbidden(*_args, **_kwargs): pytest.fail("Revoked first-run reached SSH")
    monkeypatch.setattr(FixedProcess, "call", forbidden)
    from tb4.private_settings import SettingsError
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"): checker.validate(before.payload)
    assert linked.profile.read() == before and objects(v) == inventory and checker.credentials is None


def test_real_lost_after_commit_reply_is_unknown_and_same_readback_never_replays(combined, tmp_path, monkeypatch):
    v = combined; linked = connect(v, v.a, tmp_path/"owned-setup-a")
    saved, inventory = linked.profile.read(), objects(v)
    old = linked.client.read(); value = desired(old)
    original, cas = FixedProcess.call, []
    def lose(transport, raw):
        reply = original(transport, raw)
        if flat_json(raw)["operation"] == "CAS":
            cas.append(raw)
            raise RuntimeError("SYNTHETIC_LOST_AFTER_REAL_COMMIT")
        return reply
    monkeypatch.setattr(FixedProcess, "call", lose)
    assert linked.client.compare_replace(old, value) is WriteResult.UNKNOWN and len(cas) == 1
    assert linked.client.read().document() == linked.probe.verify().document() == value
    assert len(cas) == 1 and linked.profile.read() == saved and objects(v) == inventory


def test_real_first_cas_stale_forced_takeover_preserves_local_unknown_without_peer_ack(combined, tmp_path):
    v = combined
    a, b = connect(v, v.a, tmp_path/"owned-setup-a"), connect(v, v.b, tmp_path/"owned-setup-b")
    for linked in (a, b):
        current = linked.profile.read(); payload = current.payload
        payload.update(state="BLOCKED", reason="UNKNOWN_OPERATION")
        payload["operations"]["d"*64] = "UNKNOWN"
        linked.profile.save(validated(payload), expected_revision=current.revision)
    saved = a.profile.read(), b.profile.read(), objects(v)
    from tb4.drive.leadership import LEADER, FORCE
    before = a.client.read().document()
    contender = Leadership(b.client, actor=ACTORS[1], enrollment=ENROLLMENT)
    stale = contender.acquire(contender.observe(clock(220)), transition=tid("native-stale"))
    old_grant = contender.confirmed_grant(stale, contender.commit(stale, mode="START"))
    assert old_grant.epoch == 2
    successor = Leadership(a.client, actor=ACTORS[0], enrollment=ENROLLMENT)
    request_id = tid("native-forced")
    request = successor.request_force(successor.observe(clock(221)),
        request_id=request_id, user_requested=True)
    assert successor.commit(request, mode="START").outcome == "CONFIRMED"
    assert not contender.current_before_dispatch(old_grant, clock(221))
    claim = successor.claim_requested(successor.observe(clock(221)), request_id=request_id)
    new_grant = successor.confirmed_grant(claim, successor.commit(claim, mode="START"))
    assert new_grant.epoch == 3
    after = a.client.read().document()
    assert {k:v for k,v in after.items() if k != "records"} == {
        k:v for k,v in before.items() if k != "records"}
    assert {k:v for k,v in after["records"].items() if k not in {LEADER, FORCE}} == {
        k:v for k,v in before["records"].items() if k not in {LEADER, FORCE}}
    assert (a.profile.read(), b.profile.read(), objects(v)) == saved


@pytest.mark.parametrize("selected", [Purpose.FOLDER_PROBE, Purpose.FOLDER_AUTHORITY])
def test_real_hidden_saved_scope_cannot_replace_current_explicit_purpose(combined, tmp_path, monkeypatch, selected):
    v = combined; linked = connect(v, v.a, tmp_path/"owned-setup-a")
    current = linked.profile.read(); payload = current.payload
    payload["choices"]["credentials"][0]["purposes"] = [selected.value]
    linked.profile.save(validated(payload), expected_revision=current.revision)
    saved, inventory = linked.profile.read(), objects(v)
    original, calls = FixedProcess.call, []
    def observe(transport, raw):
        calls.append(transport.argv[-1])
        return original(transport, raw)
    monkeypatch.setattr(FixedProcess, "call", observe)
    if selected is Purpose.FOLDER_PROBE:
        with pytest.raises(AuthorityError, match="^HELPER_UNAVAILABLE$"): linked.client.read()
        assert not calls and linked.probe.verify()
        assert calls == ["tb4-folder-probe-v1"]
    else:
        with pytest.raises(AuthorityError, match="^PROBE_UNAVAILABLE$"): linked.probe.verify()
        assert not calls and linked.client.read()
        assert calls == ["tb4-folder-v1"]
    assert linked.profile.read() == saved and objects(v) == inventory



