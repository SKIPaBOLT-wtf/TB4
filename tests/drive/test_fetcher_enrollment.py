"""Actual protected setup/CAS adapters, synthetic authenticated peers, native local facts."""
import copy
from dataclasses import asdict, replace
import json
import os
from uuid import uuid4

import pytest

from tb4.ballpark import BallparkError
from tb4.ballpark_setup import GuidedBallpark
from tb4.ballpark_publication import Publisher
from tb4.ballpark_records import shared
from tb4.commissioning_state import Setup, validated
from tb4.commissioning_checks import native_credential_pair
from tb4.credential_contract import CredentialResolver, Purpose, Outcome
from tb4.discovery_workflow import Discovery
from tb4.discovery_catalogue import DiscoveryError
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.commissioning import frozen_plan, restored_plan
from tb4.drive.leadership import Leadership
from tb4.enrollment_records import target, binding_current
from tb4.enrollment_workflow import Enrollment, VerifiedPeer, GUIDANCE, digest, transition
from tb4.fetcher_enrollment import FetcherEnrollment
from tb4.fetcher_profile import EnrollmentError, native_snapshot
from tb4.private_settings import PrivateSettings, native_settings, SettingsError
from tb4.exchange_layout import LayoutError, encoded, slots, validate_document
from tb4.timing_contract import ActivityClock, TimingProfile
from tests.security.test_private_settings import MemoryNative
from tests.security.test_credential_contract import FixtureStore, TRUST
from test_ballpark_setup import source, confirm, proposal, FACTS, FIRST, digest as file_digest
from test_discovery_workflow import build, observation, CANARY, SCOPE
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid
from test_fetcher_profile import snapshot

KEY_CANARY = b"synthetic-external-key-material-never-copied"


def protect_fixture(path):
    # TEST ONLY, called only for newly created task-owned synthetic files.
    if os.name == "nt":
        from tests.security.test_windows_key_native import protect
        from tb4.windows_key_native import WindowsKeyNative
        protect(WindowsKeyNative(),path)
    else:
        path.chmod(0o700 if path.is_dir() else 0o600)


@pytest.fixture
def fixture(tmp_path):
    parent = tmp_path/"enrollment-native-parent"
    parent.mkdir(mode=0o700)
    protect_fixture(parent)
    root = parent/"watchdog-settings"
    return root,native_settings(root,create=True,owner_authorized=True)


class LocalCredentialProbe:
    def __init__(self, device): self.device = device
    def verify_target(self, target, trust): return target == self.device and trust == TRUST
    def fetcher_status(self, *args): raise AssertionError("credential-use callback must never run")
    fetcher_start = fetcher_status


def two_device_discovery():
    # Fresh preallocation through the real adapters, before discovery/approval.
    from test_native_commissioning import (SetupSpec, Provider, NativeCommissioning,
        BootstrapJournal, Bootstrap, seed, Journal, finish, DOMAIN, Capacity, Commissioner)
    from tb4.drive.commissioning_bootstrap import AuthorityHandle
    from tb4.watchdog.leadership_runtime import Action, Capabilities
    from test_discovery_workflow import SCOPE

    spec = SetupSpec("synthetic-root", DOMAIN, tid("two-device-enrollment-setup"),
                     ACTORS[0], "NATIVE_DOCS", Capacity(2,1,1,1))
    provider = Provider(spec)
    port = NativeCommissioning(provider,provider,spec,llm_authorized=True)
    journal = BootstrapJournal(spec)
    bootstrap = Bootstrap(spec,port,journal,owner_authorized=True)
    seed(bootstrap)
    handle = AuthorityHandle.parse(journal.read()["handle"])
    initial = Leadership(port.authority(handle),actor=ACTORS[0],enrollment=ENROLLMENT)
    grant = bootstrap.initial_grant(initial,clock())
    finish(Commissioner(spec,initial,grant,port,Journal(spec,ACTORS[0])))
    record = dict(spec=asdict(spec),authority=handle.record())
    native = MemoryNative()
    setup = Setup(PrivateSettings(native),create=True)
    setup.choose(dict(role="watchdog",storage=record,network_scope=["192.0.2.0/24"]))
    leader = Leadership(port.authority(handle),actor=setup.installation_id,
                        enrollment={**ENROLLMENT,setup.installation_id:"synthetic-discoverer"})
    plan = leader.acquire(leader.observe(clock(220)),transition=tid("discovery-takeover"))
    result = leader.commit(plan,mode="START")
    grant = leader.confirmed_grant(plan,result)
    caps = Capabilities(setup.installation_id,True,True,frozenset({Action.SCAN,Action.REGISTER}))
    kwargs = dict(storage_port=port,leadership=leader,grant=grant,clock=lambda:clock(220),
                  capabilities=lambda:caps)
    discovery = Discovery(setup,**kwargs)
    discovery.configure(SCOPE,owner_authorized=True)
    provider.calls.clear()
    return discovery,setup,provider,native,kwargs


def ready(watch_store=None, fetch_store=None, *, two=False, scope=SCOPE):
    discovery, watch, provider, native, kwargs = two_device_discovery() if two else build(watch_store,scope=scope)
    observations = [observation()]
    if two: observations.append(observation(address="192.0.2.9", hardware_hint="second-hint"))
    discovery.observe(tuple(observations))
    assert discovery.publish() == "CONFIRMED"
    origin = source()
    origin.files[FIRST][GUIDANCE] = b"synthetic enrollment guidance"
    origin.catalog["profiles"][0]["files"][GUIDANCE] = file_digest(origin.files[FIRST][GUIDANCE])
    origin.save()
    guide = GuidedBallpark(watch, source=origin, runtime=FACTS)
    guide.begin()
    if two:
        choices = proposal(guide)
        choices["devices"] = [{**choices["devices"][0], "device_id": q["device_id"]}
                              for q in guide.questions()["targets"]]
        guide.propose(choices)
        guide.confirm(topology="FLAT", at=220, owner_authorized=True)
    else: confirm(guide)
    assert Publisher(guide, discovery).publish() == "CONFIRMED"
    client_native = MemoryNative() if fetch_store is None else None
    client = Setup(fetch_store or PrivateSettings(client_native), create=True)
    client.choose(dict(role="fetcher", storage=watch.private_choices()["storage"]))
    activity = ActivityClock(220,220,new_installation=True)
    fetcher = FetcherEnrollment(client, discovery.port, runtime=lambda:snapshot(), activity=activity)
    device = target(provider.store.document, 0)[2]["device_id"]
    fetcher.select(0, device_id=device, owner_authorized=True)
    def verify(request):
        assert request == client._payload["fetcher_enrollment"]["last_report"]
        return VerifiedPeer(client.installation_id, device, request["nonce"], digest(request["profile"]),
                            discovery.clock().utc, FACTS)
    manager = Enrollment(discovery, source=origin, runtime=FACTS, verify_peer=verify)
    return manager, fetcher, provider, origin, native, client_native, kwargs


@pytest.fixture
def system():
    return ready()


def enroll(system):
    manager, client, *_ = system
    value = client.capture(observed_at=220)
    assert manager.register(value, owner_authorized=True) == "CONFIRMED"
    assert client.inspect() == "CONFIRMED"
    return value


def restart(system):
    manager, client, provider, origin, native, *_ = system
    setup = Setup(PrivateSettings(native))
    return Enrollment(Discovery(setup, **system[6]), source=origin, runtime=FACTS,
                      verify_peer=manager.verify_peer)


def attesting(manager):
    # Explicit synthetic verified endpoint for negative contract cases.
    manager.verify_peer = lambda r: VerifiedPeer(r["installation_id"], r["device_id"], r["nonce"],
                                               digest(r["profile"]), manager.discovery.clock().utc, FACTS)


def test_owner_approved_distinct_installation_changes_one_existing_catalogue(system, capsys):
    manager, client, provider, *_ = system
    before = copy.deepcopy(provider.store.document)
    objects = copy.deepcopy(provider.created)
    request = client.capture(observed_at=220)
    assert client.setup.installation_id != manager.setup.installation_id
    assert provider.store.document == before and not client.status()["enrolled"]
    with pytest.raises(EnrollmentError, match="OWNER_REQUIRED"): manager.register(request)
    assert manager.register(request, owner_authorized=True) == "CONFIRMED"
    after = provider.store.document
    assert {k for k in before["records"] if before["records"][k] != after["records"][k]} == {"target.000.catalogue"}
    body = after["records"]["target.000.catalogue"]["body"]
    assert all(body[k] == before["records"]["target.000.catalogue"]["body"][k]
               for k in ("artifacts", "discovery", "ballpark"))
    assert shared(after) == shared(before) and provider.created == objects
    assert binding_current(after, 0, client.setup.installation_id, 1)
    assert client.inspect() == "CONFIRMED" and client.status()["enrolled"]
    summary = manager.summary(now=220)
    assert summary["targets"][0]["profile"]["platform"]["os"] == "LINUX"
    assert summary["targets"][0]["profile"]["capabilities"]["script_artifacts"] is False
    assert summary["targets"][0]["execution_authorized"] is False
    assert all(s not in json.dumps(summary) for s in (CANARY, client.setup.installation_id,
               manager.setup.installation_id, "192.0.2.8", "second-hint"))
    assert capsys.readouterr() == ("", "")


def test_same_confirmed_report_is_idempotent_but_reinstall_cannot_take_its_identity(system):
    manager, client, provider, *_ = system
    request = enroll(system)
    count = provider.store.commits
    assert manager.register(request, owner_authorized=True) == "CONFIRMED"
    assert provider.store.commits == count
    new = Setup(PrivateSettings(MemoryNative()), create=True)
    new.choose(dict(role="fetcher", storage=client.setup.private_choices()["storage"]))
    replacement = FetcherEnrollment(new, manager.discovery.port, runtime=lambda:snapshot(), activity=client.activity)
    with pytest.raises(EnrollmentError, match="REINSTALL_MAINTENANCE"):
        replacement.select(0, device_id=request["device_id"], owner_authorized=True)
    assert new.installation_id != client.setup.installation_id and provider.store.commits == count


@pytest.mark.parametrize("kind", ["false-verifier", "raw-dict", "wrong-installation", "wrong-device", "wrong-digest", "old-proof", "same-watchdog", "unknown-build"])
def test_unverified_peer_or_copied_identity_never_saves_or_writes(system, kind):
    manager, client, provider, *_ = system
    request = client.capture(observed_at=220)
    before = copy.deepcopy(provider.store.document)
    own = copy.deepcopy(manager.setup._payload)
    proof = VerifiedPeer(client.setup.installation_id, request["device_id"], request["nonce"], digest(request["profile"]),220,FACTS)
    if kind == "false-verifier": manager.verify_peer = lambda r: False
    elif kind == "raw-dict": manager.verify_peer = lambda r: {"verified":True}
    elif kind == "wrong-installation": manager.verify_peer = lambda r: replace(proof, installation_id=str(uuid4()))
    elif kind == "wrong-device": manager.verify_peer = lambda r: replace(proof, device_id=str(uuid4()))
    elif kind == "wrong-digest": manager.verify_peer = lambda r: replace(proof, profile_sha256="f"*64)
    elif kind == "old-proof": manager.verify_peer = lambda r: replace(proof, verified_at=219)
    elif kind == "same-watchdog": request["installation_id"] = manager.setup.installation_id
    elif kind == "unknown-build":
        request["profile"]["build_commit"] = "f"*40
        attesting(manager)
    with pytest.raises(EnrollmentError): manager.register(request, owner_authorized=True)
    assert provider.store.document == before and manager.setup._payload == own


def test_actual_runtime_policy_not_saved_watchdog_or_fetcher_proposal_drives_report(system):
    manager, client, *_ = system
    client.setup.choose({"timing": {**client.setup.private_choices()["timing"], "idle_policy":"EXIT"}})
    value = client.capture(observed_at=220)
    assert value["profile"]["timing"]["idle_policy"] == "SLOW"
    assert value["profile"]["platform"]["os"] == "LINUX"
    assert manager.setup.private_choices()["descriptor"]["devices"][0]["platform"]["os"] == "UNKNOWN"


def test_profile_revision_and_freshness_are_effective_not_a_ready_guess(system):
    manager, client, provider, *_ = system
    enroll(system)
    client.activity.sample(221,221)
    manager.discovery.clock = lambda:clock(221)
    updated = client.capture(observed_at=221, holds={"unknown":True})
    assert updated["profile"]["revision"] == 2
    assert manager.update(updated) == "CONFIRMED" and client.inspect() == "CONFIRMED"
    summary = manager.summary(now=221)["targets"][0]
    assert summary["profile"]["polling"] == dict(mode="BUSY",poll_s=20,observed_at=221,clock_known=True,next_check_at=241)
    assert summary["freshness"] == "FRESH" and not summary["execution_authorized"]
    assert manager.summary(now=521)["targets"][0]["fetcher_liveness"] == "UNKNOWN"
    assert manager.summary(now=220)["targets"][0]["freshness"] == "CLOCK_UNCERTAIN"


@pytest.mark.parametrize("kind", ["stale-revision", "revision-gap", "old-sample", "future", "expired", "changed-device", "alias-conflict", "capacity"])
def test_conflicting_or_stale_report_preserves_confirmed_state(system, kind):
    manager, client, provider, *_ = system
    enroll(system)
    client.activity.sample(221,221)
    manager.discovery.clock = lambda:clock(221)
    value = client.capture(observed_at=221)
    attesting(manager)
    if kind == "stale-revision": value["profile"]["revision"] = 1
    elif kind == "revision-gap": value["profile"]["revision"] = 3
    elif kind in {"old-sample","future","expired"}:
        at = {"old-sample":220, "future":222, "expired":0}[kind]
        value["profile"]["polling"].update(observed_at=at,next_check_at=at+20)
        if kind == "expired": manager.discovery.clock = lambda:clock(321)
    elif kind == "changed-device": value["device_id"] = str(uuid4())
    elif kind == "alias-conflict": provider.store.document["records"]["target.000.catalogue"]["body"]["discovery"]["alias"] = "foreign-alias"
    elif kind == "capacity": value["slot"] = 63
    before = copy.deepcopy(provider.store.document)
    own = copy.deepcopy(manager.setup._payload)
    with pytest.raises((EnrollmentError,BallparkError,DiscoveryError,SettingsError,AuthorityError)):
        manager.update(value)
    assert provider.store.document == before and manager.setup._payload == own


def test_same_installation_cannot_enroll_second_approved_device_or_rebind_local_choices():
    system = ready(two=True)
    manager, client, provider, *_ = system
    request = enroll(system)
    second = target(provider.store.document, 1)[2]
    other = {**request,"slot":1,"device_id":second["device_id"]}
    attesting(manager)
    count = provider.store.commits
    with pytest.raises(EnrollmentError, match="INSTALLATION_DUPLICATE"):
        manager.register(other, owner_authorized=True)
    with pytest.raises(EnrollmentError, match="MAINTENANCE_REQUIRED"):
        client.select(1, device_id=second["device_id"], owner_authorized=True)
    assert provider.store.commits == count


def test_discovery_alone_or_unselected_device_has_no_enrollment_grant(system):
    manager, client, provider, *_ = system
    request = client.capture(observed_at=220)
    provider.store.document["records"]["global.registry"]["body"]["slots"] = []
    before = copy.deepcopy(provider.store.document)
    with pytest.raises((EnrollmentError,BallparkError,DiscoveryError)):
        manager.register(request, owner_authorized=True)
    assert provider.store.document == before and not client.status()["enrolled"]


def test_lost_reply_restart_only_inspects_exact_operation_after_takeover(system):
    manager, client, provider, *_ = system
    request = client.capture(observed_at=220)
    backend = manager.discovery.leader.backend
    read = backend.read
    def lose():
        backend.read = lambda:(_ for _ in ()).throw(AuthorityError("UNAVAILABLE"))
        raise TimeoutError(CANARY)
    provider.store.after_write = lose
    assert manager.register(request, owner_authorized=True) == "UNKNOWN"
    backend.read, provider.store.after_write = read, None
    leader = Leadership(backend, actor=ACTORS[1], enrollment=manager.discovery.leader.enrollment)
    plan = leader.acquire(leader.observe(clock(340)),transition=tid("enrollment-takeover"))
    assert leader.commit(plan, mode="START").outcome == "CONFIRMED"
    resumed = restart(system)
    count = provider.store.commits
    with pytest.raises(EnrollmentError, match="INSPECT_REQUIRED"):
        resumed.register(request,owner_authorized=True)
    assert resumed.inspect() == "CONFIRMED" and provider.store.commits == count
    assert client.inspect() == "CONFIRMED"


def test_unsent_durable_intent_cancelled_restart_remains_unknown_without_resend(system):
    manager, client, provider, *_ = system
    save = manager._save
    def interrupted(state):
        save(state)
        if state["pending"]: raise RuntimeError("synthetic-before-send")
    manager._save = interrupted
    before = copy.deepcopy(provider.store.document)
    with pytest.raises(RuntimeError): manager.register(client.capture(observed_at=220), owner_authorized=True)
    manager.setup.cancel()
    count = provider.store.commits
    assert restart(system).inspect() == "UNKNOWN" and provider.store.document == before
    assert provider.store.commits == count


@pytest.mark.parametrize("part", ["authority", "mode", "request", "operation", "owner", "protected", "before", "after"])
def test_persisted_pending_tamper_is_rejected_before_recovery(system, part):
    manager, client, provider, *_ = system
    save = manager._save
    def stopped(state):
        save(state)
        if state["pending"]: raise RuntimeError("synthetic-stopped")
    manager._save = stopped
    with pytest.raises(RuntimeError): manager.register(client.capture(observed_at=220), owner_authorized=True)
    payload = copy.deepcopy(manager.setup._payload)
    state = payload["enrollments"]
    pending = state["pending"]
    if part == "authority": state["authority"]["object_id"] = "foreign-root"
    elif part == "mode": pending["mode"] = "PROFILE"
    elif part == "request": pending["request"]["installation_id"] = str(uuid4())
    elif part == "operation": pending["operation"] = "f"*64
    else:
        plan = restored_plan(pending["plan"],None)
        if part == "owner": plan = replace(plan,owner=replace(plan.owner,owner=str(uuid4())))
        else:
            value = json.loads(getattr(plan,part))
            if part == "protected": value.pop("global.registry")
            elif part == "before": value["target.000.catalogue"]["generation"] += 1
            elif part == "after": value["target.000.catalogue"]["body"]["enrollment"][1] = str(uuid4())
            plan = replace(plan,**{part:encoded(value)})
        pending["plan"] = frozen_plan(plan)
    with pytest.raises(SettingsError): validated(payload)


def test_revocation_preserves_unknown_work_history_and_prevents_old_binding(system):
    manager, client, provider, *_ = system
    enroll(system)
    provider.store.document["records"]["target.000.work"] = dict(generation=7,operation_id="synthetic-unknown",retention="UNKNOWN",body={"unknown":True})
    before = copy.deepcopy(provider.store.document)
    assert manager.revoke(0,installation_id=client.setup.installation_id,expected_revision=1,owner_authorized=True) == "CONFIRMED"
    after = provider.store.document
    assert all(after["records"][k] == v for k,v in before["records"].items() if k != "target.000.catalogue")
    assert after["records"]["target.000.catalogue"]["generation"] > before["records"]["target.000.catalogue"]["generation"]
    assert not binding_current(after,0,client.setup.installation_id,1)
    assert client.inspect() == "REVOKED" and not client.status()["enrolled"]
    count = provider.store.commits
    assert manager.revoke(0,installation_id=client.setup.installation_id,expected_revision=1,owner_authorized=True) == "CONFIRMED"
    assert provider.store.commits == count


def test_native_file_restart_keeps_both_distinct_installations_and_receipts(fixture):
    root, watch_store = fixture
    client_root = root.parent/"fetcher-settings"
    client_store = native_settings(client_root,create=True,owner_authorized=True)
    system = ready(watch_store,client_store)
    manager, client, provider, origin, *_ = system
    enroll(system)
    watch = Setup(native_settings(root))
    fetch = Setup(native_settings(client_root))
    assert watch.installation_id != fetch.installation_id
    assert watch._payload["enrollments"]["active"]["0"]["enrollment"][1] == fetch.installation_id
    resumed = FetcherEnrollment(fetch,manager.discovery.port,runtime=lambda:native_snapshot(
        launch_mode="DESKTOP_SESSION",build_commit=FACTS.build_commit),activity=client.activity)
    assert resumed.inspect() == "CONFIRMED" and not resumed.status()["runtime_active"]


def test_native_own_credentials_availability_is_not_copied_or_exposed(fixture):
    root, store = fixture
    system = ready(store)
    manager, client, *_ = system
    enroll(system)
    device = client.setup._payload["fetcher_enrollment"]["device_id"]
    path = root.parent/"synthetic-enrollment-key"
    path.write_bytes(KEY_CANARY)
    protect_fixture(path)
    key_store, resolver = native_credential_pair(manager.setup.installation_id,runner=LocalCredentialProbe(device),clock=lambda:220)
    extra = dict(interactive_required=False) if os.name == "nt" else dict(access_mode="existing_key",launch_mode="headless")
    ref = key_store.select(path=str(path),target_id=device,target_trust=TRUST,purposes=frozenset(Purpose),expires_at=500,owner_authorized=True,**extra)
    handle = resolver.enroll(target_id=device,target_trust=TRUST,store_locator=ref,purposes=frozenset(Purpose),expires_at=500,owner_authorized=True)
    manager.setup.persist_credentials(key_store,resolver,[dict(handle=handle,target_id=device,target_trust=TRUST,purposes=[p.value for p in Purpose])])
    summary = manager.summary(resolver,now=220)
    assert summary["targets"][0]["watchdog_credentials"]["FETCHER_STATUS"]["available"]
    assert all(s not in json.dumps(summary) for s in (handle,str(path),TRUST,manager.setup.installation_id))
    resolver.revoke(handle,owner_authorized=True)
    assert manager.summary(resolver,now=220)["targets"][0]["watchdog_credentials"]["FETCHER_START"]["outcome"] == "REVOKED"
    foreign = CredentialResolver(client.setup.installation_id,FixtureStore(client.setup.installation_id),clock=lambda:220)
    with pytest.raises(EnrollmentError,match="CREDENTIAL_INSTALLATION"): manager.summary(foreign,now=220)


def test_whole_record_headroom_rejection_does_not_reset_or_truncate(system):
    from test_fetcher_profile import profile
    manager, client, provider, *_ = system
    value = client.capture(observed_at=220)
    value["profile"] = profile()
    for info in value["profile"]["interpreters"].values():
        info.update(state="ENABLED",version=[65535,65535,65535])
    document = copy.deepcopy(provider.store.document)
    row = document["records"]["target.000.catalogue"]
    row["generation"] = 2**63-2
    for ref in row["body"]["artifacts"].values(): ref["id"] = "x"*128
    validate_document(document)
    before = copy.deepcopy(document)
    with pytest.raises(LayoutError): transition(document,value,mode="REGISTER",operation="a"*64)
    assert document == before and manager.setup._payload.get("enrollments") is None


def test_all64_preallocated_targets_keep_complete_profiles_within_existing_budgets(system):
    from dataclasses import asdict
    from uuid import UUID
    from tb4.ballpark import catalogue
    from tb4.ballpark_records import compact as compact_device
    from tb4.exchange_layout import Capacity, empty_document
    from test_fetcher_profile import profile
    manager, client, provider, *_ = system
    original = provider.store.document
    capacity = Capacity(64,1,1,1)
    document = empty_document(original["domain_id"],capacity)
    for name in ("global.registry","global.settings","global.commissioning"):
        document["records"][name] = copy.deepcopy(original["records"][name])
    local = copy.deepcopy(manager.setup.private_choices()["descriptor"])
    template = local["devices"][0]
    local["devices"] = []
    for i in range(64):
        device = {**copy.deepcopy(template),"device_id":str(UUID(int=i+100)),"alias":f"device-{i:03d}"}
        device["display_name"] = device["alias"]
        local["devices"].append(device)
        row = copy.deepcopy(original["records"]["target.000.catalogue"])
        body = row["body"]
        body["discovery"].update(device_id=device["device_id"],alias=device["alias"])
        body["ballpark"] = compact_device(device,1)
        for kind, ref in body["artifacts"].items(): ref["id"] = f"synthetic-{kind}-{i}"
        document["records"][f"target.{i:03d}.catalogue"] = row
    meta = document["records"]["global.registry"]["body"]
    meta.update(slots=list(range(64)),sha256=digest(catalogue(local)))
    keys = set(document["records"])
    for i, device in enumerate(local["devices"]):
        request = dict(slot=i,device_id=device["device_id"],installation_id=str(UUID(int=i+500)),
                       nonce="a"*32,expected_enrollment_revision=0,profile=profile())
        document["records"].update(transition(document,request,mode="REGISTER",operation="a"*64))
    validate_document(document)
    assert set(document["records"]) == keys and shared(document) == catalogue(local)
    for key,budget in slots(capacity).items(): assert len(encoded({key:document["records"][key]})) <= budget


def test_discovery_refresh_preserves_enrollment_and_effective_profile():
    system = ready(scope=replace(SCOPE,methods=frozenset({"NEIGHBOR_CACHE","ICMP"})))
    manager, client, provider, *_ = system
    enroll(system)
    prior = copy.deepcopy(provider.store.document["records"]["target.000.catalogue"]["body"])
    manager.discovery.clock = lambda:clock(221)
    assert manager.discovery.observe((observation(source="ICMP",observed_at=221,online=True),)) == ("OBSERVED",)
    assert manager.discovery.publish() == "CONFIRMED"
    body = provider.store.document["records"]["target.000.catalogue"]["body"]
    assert body["enrollment"] == prior["enrollment"] and body["fetcher"] == prior["fetcher"]
    assert body["ballpark"] == prior["ballpark"] and shared(provider.store.document)


@pytest.mark.parametrize("force", [False,True])
def test_new_owner_or_forced_request_stops_old_enrollment_without_ack_barrier(system, force):
    manager, client, provider, *_ = system
    request = client.capture(observed_at=220)
    leader = Leadership(manager.discovery.leader.backend,actor=ACTORS[1],
                        enrollment=manager.discovery.leader.enrollment)
    if force:
        plan = leader.request_force(leader.observe(clock(221)),request_id=tid("force-enrollment"),user_requested=True)
    else:
        plan = leader.acquire(leader.observe(clock(340)),transition=tid("take-enrollment"))
    assert leader.commit(plan,mode="START").outcome == "CONFIRMED"
    before = copy.deepcopy(provider.store.document)
    with pytest.raises(DiscoveryError,match="SUPERSEDED"): manager.register(request,owner_authorized=True)
    assert provider.store.document == before and manager.setup._payload.get("enrollments") is None


@pytest.mark.parametrize("failure", ["stage","promote","readback"])
def test_private_intent_failure_never_reaches_authority(system, failure):
    manager, client, provider, origin, native, *_ = system
    request = client.capture(observed_at=220)
    before = copy.deepcopy(provider.store.document)
    promote = native.promote
    if failure == "readback":
        def lost():
            promote()
            native.failure = "readback"
        native.promote = lost
    else:
        native.failure = failure
    with pytest.raises(SettingsError): manager.register(request,owner_authorized=True)
    assert provider.store.document == before
    native.failure, native.promote = None, promote
    PrivateSettings(native).recover_pending()
    assert restart(system).inspect() == "UNKNOWN" and provider.store.document == before


def test_peer_change_after_durable_intent_is_inspection_only(system):
    manager, client, provider, *_ = system
    request = client.capture(observed_at=220)
    save = manager._save
    def change_peer(state):
        save(state)
        if state["pending"]: manager.verify_peer = lambda r:False
    manager._save = change_peer
    before = copy.deepcopy(provider.store.document)
    with pytest.raises(EnrollmentError,match="PEER_UNVERIFIED"): manager.register(request,owner_authorized=True)
    assert provider.store.document == before and restart(system).inspect() == "UNKNOWN"


@pytest.mark.parametrize("field", ["role","storage","network_scope","descriptor"])
def test_general_setup_or_rollback_cannot_erase_registration(system, field):
    manager, client, provider, *_ = system
    enroll(system)
    before = copy.deepcopy(manager.setup._payload)
    patch = {"role":"fetcher","storage":None,"network_scope":[],"descriptor":None}
    with pytest.raises(SettingsError,match="BINDING_FROZEN"): manager.setup.choose({field:patch[field]})
    with pytest.raises(SettingsError,match="ROLLBACK_UNSAFE"): manager.setup.rollback_choices(stopped=True)
    assert manager.setup._payload == before
