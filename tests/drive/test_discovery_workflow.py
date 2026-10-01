"""Actual commissioning/CAS adapters over a synthetic service; no live network."""
import copy
import json
import os

import pytest

from tb4.commissioning_state import Setup, validated
from tb4.discovery_catalogue import DiscoveryError, Interface, Observation, Scope, TrustView
from tb4.discovery_state import parse_scope, scope_record
from tb4.discovery_workflow import Discovery
from tb4.drive.leadership import Leadership
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.private_settings import PrivateSettings, SettingsError, native_settings
from tb4.watchdog.leadership_runtime import Action, Capabilities
from tests.security.test_private_settings import MemoryNative
from test_first_run_storage import prepared
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid

SCOPE = Scope((Interface("synthetic-interface", 7, ("192.0.2.0/24",), "LAN"),))
CANARY = "SYNTHETIC_PRIVATE_DISCOVERY_CANARY"


def observation(**patch):
    return Observation(**(dict(interface_index=7, address="192.0.2.8", source="NEIGHBOR_CACHE",
                               observed_at=220, valid_for_s=60, hardware_hint="synthetic-hint",
                               name_hint=CANARY) | patch))


def build(store=None):
    native = MemoryNative() if store is None else None
    setup = Setup(store or PrivateSettings(native), create=True)
    spec, provider, port, record = prepared()
    setup.choose(dict(role="watchdog", storage=record, network_scope=["192.0.2.0/24"]))
    enrollment = {**ENROLLMENT, setup.installation_id: "synthetic-discoverer"}
    backend = port.authority(AuthorityHandle.parse(record["authority"]))
    leader = Leadership(backend, actor=setup.installation_id, enrollment=enrollment)
    plan = leader.acquire(leader.observe(clock(220)), transition=tid("discovery-takeover"))
    report = leader.commit(plan, mode="START")
    grant = leader.confirmed_grant(plan, report)
    caps = Capabilities(setup.installation_id, True, True, frozenset({Action.SCAN, Action.REGISTER}))
    kwargs = dict(storage_port=port, leadership=leader, grant=grant, clock=lambda: clock(220),
                  capabilities=lambda: caps)
    workflow = Discovery(setup, **kwargs)
    workflow.configure(SCOPE, owner_authorized=True)
    provider.calls.clear()
    return workflow, setup, provider, native, kwargs


@pytest.fixture
def system():
    return build()


def test_persist_before_publication_restart_stable_alias_and_minimal_projection(system, capsys):
    flow, setup, provider, native, kwargs = system
    created = copy.deepcopy(provider.created)
    before = copy.deepcopy(provider.store.document["records"])
    assert flow.observe((observation(),)) == ("OBSERVED",)
    image = copy.deepcopy(setup._payload["discovery"]["image"])
    assert all(before[k] == provider.store.document["records"][k] for k in before)
    restarted = Discovery(Setup(PrivateSettings(native)), **kwargs)
    assert restarted.publish() == "CONFIRMED"
    rows = provider.store.document["records"]
    body = rows["target.000.catalogue"]["body"]
    assert body["discovery"]["device_id"] == image["entries"][0]["device_id"]
    assert body["discovery"]["alias"] == "device-001"
    assert body["discovery"]["trust"] == "UNTRUSTED" and body["enrollment"] == "UNENROLLED"
    assert body["artifacts"] == before["target.000.catalogue"]["body"]["artifacts"]
    assert all(rows[k] == before[k] for k in before if k != "target.000.catalogue")
    assert provider.created == created and all(name == "files.get" for name, _ in provider.calls)
    public = json.dumps(body) + json.dumps(restarted.status())
    assert all(private not in public for private in (CANARY, "192.0.2.8", "synthetic-interface", "synthetic-hint"))
    assert restarted.publish() == "NO_CHANGE"
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("field,value", [("role", "fetcher"), ("storage", None),
    ("network_scope", []), ("storage_request", {"mode": "NATIVE_DOCS", "location": "synthetic-other"})])
def test_discovery_binding_cannot_be_reconfigured_by_general_setup(system, field, value):
    flow, setup, *_ = system
    before = copy.deepcopy(setup._payload)
    with pytest.raises(SettingsError, match="BINDING_FROZEN"):
        setup.choose({field: value})
    assert setup._payload == before


def test_cancel_resume_and_rollback_preserve_mappings(system):
    flow, setup, provider, native, kwargs = system
    flow.observe((observation(),))
    with pytest.raises(SettingsError, match="ROLLBACK_UNSAFE"):
        setup.rollback_choices(stopped=True)
    image = copy.deepcopy(setup._payload["discovery"]["image"])
    setup.cancel()
    restarted = Setup(PrivateSettings(native))
    flow = Discovery(restarted, **kwargs)
    with pytest.raises(DiscoveryError, match="CANCELLED"):
        flow.publish()
    restarted.resume()
    assert restarted._payload["discovery"]["image"] == image
    assert flow.publish() == "CONFIRMED"


@pytest.mark.parametrize("failure", ["stage", "promote", "readback"])
def test_failed_local_persistence_never_sends_shared_write(system, failure):
    flow, setup, provider, native, kwargs = system
    flow.observe((observation(),))
    commits = provider.store.commits
    if failure == "readback":
        promote = native.promote
        def lose_readback():
            promote()
            native.failure = "readback"
        native.promote = lose_readback
    else:
        native.failure = failure
    with pytest.raises(SettingsError):
        flow.publish()
    assert provider.store.commits == commits
    native.failure = None
    if failure == "readback":
        native.promote = promote
    store = PrivateSettings(native)
    store.recover_pending()
    restored = Discovery(Setup(store), **kwargs)
    assert restored.status()["publication_pending"]
    assert restored.inspect() == "UNKNOWN"
    assert provider.store.commits == commits
    with pytest.raises(DiscoveryError, match="INSPECT_REQUIRED"):
        restored.publish()


def test_lost_reply_restart_is_read_only_then_confirms_same_plan(system):
    flow, setup, provider, native, kwargs = system
    flow.observe((observation(),))
    old_read = kwargs["leadership"].backend.read
    from tb4.drive.docs_authority import AuthorityError
    def lose():
        kwargs["leadership"].backend.read = lambda: (_ for _ in ()).throw(AuthorityError("UNAVAILABLE"))
        raise TimeoutError(CANARY)
    provider.store.after_write = lose
    assert flow.publish() == "UNKNOWN"
    count = provider.store.commits
    kwargs["leadership"].backend.read = old_read
    provider.store.after_write = None
    restarted = Discovery(Setup(PrivateSettings(native)), **kwargs)
    assert restarted.inspect() == "CONFIRMED"
    assert not restarted.status()["publication_pending"] and provider.store.commits == count


@pytest.mark.parametrize("force", [False, True])
def test_stale_or_forced_takeover_stops_old_publication_without_all_sink_barrier(system, force):
    flow, setup, provider, native, kwargs = system
    flow.observe((observation(),))
    old = copy.deepcopy(provider.store.document["records"]["target.000.catalogue"])
    leader = Leadership(kwargs["leadership"].backend, actor=ACTORS[1], enrollment={
        **ENROLLMENT, setup.installation_id: "synthetic-discoverer"})
    if force:
        plan = leader.request_force(leader.observe(clock(221)), request_id=tid("force-discovery"), user_requested=True)
    else:
        plan = leader.acquire(leader.observe(clock(340)), transition=tid("stale-discovery"))
    assert leader.commit(plan, mode="START").outcome == "CONFIRMED"
    with pytest.raises(DiscoveryError, match="SUPERSEDED"):
        flow.publish()
    assert provider.store.document["records"]["target.000.catalogue"] == old


def test_takeover_after_pending_save_blocks_cas_and_keeps_exact_inspection(system):
    flow, setup, provider, native, kwargs = system
    flow.observe((observation(),))
    save = flow._save
    def takeover(value):
        save(value)
        if value["pending"] is not None:
            owner = Leadership(kwargs["leadership"].backend, actor=ACTORS[1], enrollment={
                **ENROLLMENT, setup.installation_id: "synthetic-discoverer"})
            plan = owner.acquire(owner.observe(clock(340)), transition=tid("after-durability"))
            assert owner.commit(plan, mode="START").outcome == "CONFIRMED"
    flow._save = takeover
    with pytest.raises(DiscoveryError, match="SUPERSEDED"):
        flow.publish()
    resumed = Discovery(Setup(PrivateSettings(native)), **kwargs)
    assert resumed.inspect() == "SUPERSEDED"
    assert "discovery" not in provider.store.document["records"]["target.000.catalogue"]["body"]


def test_retained_work_blocks_new_identity_but_is_never_erased(system):
    flow, setup, provider, *_ = system
    flow.observe((observation(),))
    retained = dict(generation=4, operation_id="synthetic-unknown", retention="UNKNOWN", body={"unknown": True})
    provider.store.document["records"]["target.000.work"] = retained
    with pytest.raises(DiscoveryError, match="SLOT_RETAINED"):
        flow.publish()
    assert provider.store.document["records"]["target.000.work"] == retained


def test_existing_identity_refresh_preserves_unknown_work(system):
    flow, setup, provider, *_ = system
    flow.observe((observation(),)); flow.publish()
    retained = dict(generation=4, operation_id="synthetic-unknown", retention="UNKNOWN", body={"unknown": True})
    provider.store.document["records"]["target.000.work"] = retained
    flow.clock = lambda: clock(221)
    flow.observe((observation(observed_at=221),))
    assert flow.publish() == "NO_CHANGE"  # Cached presence cannot invent online proof.
    assert provider.store.document["records"]["target.000.work"] == retained


def test_full_quarantine_preserves_foreign_record_and_local_evidence(system):
    flow, setup, provider, *_ = system
    flow.observe((observation(),))
    flow.observe((observation(address="192.0.2.9", hardware_hint="another"),))
    foreign = dict(generation=8, operation_id="other", retention="UNREAD", body={"retained": True})
    provider.store.document["records"]["quarantine.000"] = foreign
    with pytest.raises(DiscoveryError, match="QUARANTINE_FULL"):
        flow.publish()
    assert provider.store.document["records"]["quarantine.000"] == foreign
    assert flow.status()["quarantined"] == 1


def test_quarantine_uses_one_existing_slot_with_no_private_observation(system):
    flow, setup, provider, *_ = system
    flow.observe((observation(), observation(address="192.0.2.9", hardware_hint="another")))
    assert flow.publish() == "CONFIRMED"
    body = provider.store.document["records"]["quarantine.000"]["body"]
    assert body == dict(schema_version=1, kind="DISCOVERY_QUARANTINE", reason="CAPACITY_FULL")
    assert flow.publish() == "NO_CHANGE"


@pytest.mark.parametrize("case", ["installation", "domain", "capacity", "scope", "field"])
def test_copied_or_extended_private_package_is_rejected(system, case):
    flow, setup, *_ = system
    value = copy.deepcopy(setup._payload)
    package = value["discovery"]
    if case == "installation": package["image"]["installation_id"] = ACTORS[2]
    elif case == "domain": package["image"]["domain_id"] = ACTORS[2]
    elif case == "capacity": package["image"]["entries"].append(None)
    elif case == "scope": package["scope"]["interfaces"][0]["networks"] = ["198.51.100.0/24"]
    else: package["unexpected"] = CANARY
    with pytest.raises(SettingsError, match="SETUP_SCHEMA"):
        validated(value)


def test_legacy_payload_without_package_still_validates():
    setup = Setup(PrivateSettings(MemoryNative()), create=True)
    assert validated(setup._payload) == setup._payload


def test_adopted_shared_identity_does_not_import_remote_trust(system):
    flow, setup, provider, *_ = system
    flow.observe((observation(),)); flow.publish()
    saved = copy.deepcopy(provider.store.document["records"]["target.000.catalogue"]["body"]["discovery"])
    saved["trust"] = "ENROLLED"
    provider.store.document["records"]["target.000.catalogue"]["body"]["discovery"] = saved
    from tb4.discovery_catalogue import Catalogue, new_image
    catalogue = Catalogue(new_image(setup.installation_id, provider.spec.domain_id, capacity=1, quarantine_capacity=1))
    flow._adopt(catalogue, provider.store.document)
    projected = catalogue.shared(now=220)[0]
    assert projected["device_id"] == saved["device_id"] and projected["trust"] == "UNTRUSTED"
    assert projected["network"]["value"] == "UNKNOWN"


def test_conflicting_shared_identity_does_not_reassign_private_mapping(system):
    flow, setup, provider, *_ = system
    flow.observe((observation(),)); flow.publish()
    image = copy.deepcopy(setup._payload["discovery"]["image"])
    provider.store.document["records"]["target.000.catalogue"]["body"]["discovery"]["device_id"] = ACTORS[2]
    with pytest.raises(DiscoveryError, match="IDENTITY_CONFLICT"):
        flow.observe((observation(),))
    assert setup._payload["discovery"]["image"] == image


def test_selected_scope_and_capabilities_precede_any_collection(system):
    flow, setup, provider, *_ = system
    class Port:
        calls = 0
        def inspect(self, interface, *, timeout):
            assert interface == SCOPE.interfaces[0]
            self.calls += 1
        def read(self, interface, *, timeout):
            self.calls += 1
            return (("192.0.2.8", "hint"), ("198.51.100.8", CANARY))
    port = Port()
    assert flow.collect(port)["status"] == "COMPLETE"
    assert port.calls == 3 and flow.status()["used"] == 1
    flow.capabilities = lambda: Capabilities(setup.installation_id, True, False, frozenset())
    with pytest.raises(DiscoveryError, match="NOT_AUTHORIZED"):
        flow.collect(port)
    assert port.calls == 3


def test_scope_round_trip_is_closed_and_not_an_expansion():
    assert parse_scope(scope_record(SCOPE)) == SCOPE
    value = scope_record(SCOPE)
    value["methods"].append("NEIGHBOR_CACHE")
    with pytest.raises(DiscoveryError):
        parse_scope(value)


@pytest.mark.skipif(os.name != "nt" and not __import__("sys").platform.startswith("linux"), reason="native settings OS")
def test_actual_native_settings_restart_keeps_discovery_without_per_device_files(tmp_path):
    parent = tmp_path / "fresh-protected-parent"
    parent.mkdir(mode=0o700)
    if os.name == "nt":
        from tests.security.test_windows_key_native import protect
        from tb4.windows_key_native import WindowsKeyNative
        protect(WindowsKeyNative(), parent)
    root = parent / "settings"
    flow, setup, provider, _, kwargs = build(native_settings(root, create=True, owner_authorized=True))
    before = {p.name for p in root.iterdir()}
    flow.observe((observation(),))
    image = copy.deepcopy(setup._payload["discovery"]["image"])
    restarted = Discovery(Setup(native_settings(root)), **kwargs)
    assert restarted.publish() == "CONFIRMED"
    assert restarted.setup._payload["discovery"]["image"] == image
    assert {p.name for p in root.iterdir()} == before
