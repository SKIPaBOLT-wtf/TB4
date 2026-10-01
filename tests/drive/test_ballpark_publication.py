"""Guarded native Docs CAS adapter over synthetic storage; no live deployment."""
import copy
import json
import os

import pytest

from tb4.ballpark import BallparkError, catalogue
from tb4.ballpark_publication import Publisher
from tb4.ballpark_records import shared
from tb4.ballpark_setup import GuidedBallpark
from tb4.commissioning_state import Setup, validated
from tb4.discovery_catalogue import DiscoveryError
from tb4.discovery_workflow import Discovery
from tb4.drive.commissioning import frozen_plan, restored_plan
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.leadership import Leadership
from tb4.exchange_layout import LayoutError, encoded
from tb4.instructions import InstructionError
from tb4.private_settings import PrivateSettings, SettingsError, native_settings
from test_ballpark_setup import source, confirm, proposal, FACTS
from test_discovery_workflow import build, observation, CANARY
from test_native_leadership import ACTORS, ENROLLMENT, clock, tid


def ready(store=None):
    discovery, setup, provider, native, kwargs = build(store)
    discovery.observe((observation(),))
    assert discovery.publish() == "CONFIRMED"
    origin = source()
    guide = GuidedBallpark(setup, source=origin, runtime=FACTS)
    guide.begin()
    confirm(guide)
    pub = Publisher(guide, discovery)
    return pub, guide, discovery, setup, provider, native, kwargs, origin


@pytest.fixture
def system():
    return ready()


def restart(system):
    pub, guide, discovery, setup, provider, native, kwargs, origin = system
    new_setup = Setup(PrivateSettings(native))
    return Publisher(GuidedBallpark(new_setup, source=origin, runtime=FACTS), Discovery(new_setup, **kwargs))


def lose_reply(system):
    pub, guide, discovery, setup, provider, *_ = system
    read = discovery.leader.backend.read
    def lose():
        discovery.leader.backend.read = lambda: (_ for _ in ()).throw(AuthorityError("UNAVAILABLE"))
        raise TimeoutError(CANARY)
    provider.store.after_write = lose
    assert pub.publish() == "UNKNOWN"
    discovery.leader.backend.read = read
    provider.store.after_write = None


def test_atomic_minimal_revision_preserves_artifacts_discovery_and_unknown_work(system, capsys):
    pub, guide, discovery, setup, provider, *_ = system
    unknown = dict(generation=9, operation_id="synthetic-unknown-work", retention="UNKNOWN", body={"unknown": True})
    provider.store.document["records"]["target.000.work"] = unknown
    before = copy.deepcopy(provider.store.document)
    candidate = copy.deepcopy(setup._payload["ballpark_draft"]["candidate"])
    decision = copy.deepcopy(setup._payload["ballpark_draft"]["decision"])
    writes, objects = provider.store.commits, copy.deepcopy(provider.created)
    assert pub.publish() == "CONFIRMED"
    assert provider.store.commits == writes + 1 and provider.created == objects
    after = provider.store.document
    assert shared(after) == catalogue(candidate)
    assert setup.private_choices()["descriptor"] == candidate
    assert setup._payload["ballpark_publication"]["active"]["decision"] == decision
    assert setup._payload["ballpark_draft"] is None
    assert {k for k in before["records"] if before["records"][k] != after["records"][k]} == {
        "target.000.catalogue", "global.registry", "global.settings"}
    for key, value in before["records"]["target.000.catalogue"]["body"].items():
        assert after["records"]["target.000.catalogue"]["body"][key] == value
    public = json.dumps(pub.view(now=220)) + json.dumps(after["records"]["global.registry"])
    assert all(v not in public for v in (CANARY, setup.installation_id, "192.0.2.8", "synthetic-hint"))
    assert capsys.readouterr() == ("", "")


def test_lost_reply_keeps_old_active_then_restart_only_inspects_exact_revision(system):
    pub, guide, discovery, setup, provider, *_ = system
    lose_reply(system)
    assert setup.private_choices()["descriptor"] is None
    assert pub.view(now=220)["status"] == "PUBLICATION_UNKNOWN"
    count = provider.store.commits
    resumed = restart(system)
    with pytest.raises(BallparkError, match="INSPECT_REQUIRED"): resumed.publish()
    assert resumed.inspect() == "CONFIRMED"
    assert provider.store.commits == count and resumed.view(now=220)["status"] == "ACTIVE"


@pytest.mark.parametrize("force", [False, True])
def test_new_owner_or_force_request_blocks_old_owner_without_sink_ack_barrier(system, force):
    pub, guide, discovery, setup, provider, *_ = system
    leader = Leadership(discovery.leader.backend, actor=ACTORS[1], enrollment={
        **ENROLLMENT, setup.installation_id: "synthetic-discoverer"})
    if force:
        plan = leader.request_force(leader.observe(clock(221)), request_id=tid("force-ballpark"), user_requested=True)
    else:
        plan = leader.acquire(leader.observe(clock(340)), transition=tid("takeover-ballpark"))
    assert leader.commit(plan, mode="START").outcome == "CONFIRMED"
    before = copy.deepcopy(provider.store.document)
    with pytest.raises(DiscoveryError, match="SUPERSEDED"): pub.publish()
    assert provider.store.document == before and setup.private_choices()["descriptor"] is None


def test_takeover_after_applied_lost_reply_still_allows_read_only_confirmation(system):
    pub, guide, discovery, setup, provider, *_ = system
    lose_reply(system)
    leader = Leadership(discovery.leader.backend, actor=ACTORS[1], enrollment={
        **ENROLLMENT, setup.installation_id: "synthetic-discoverer"})
    plan = leader.acquire(leader.observe(clock(340)), transition=tid("after-applied-ballpark"))
    assert leader.commit(plan, mode="START").outcome == "CONFIRMED"
    count = provider.store.commits
    assert restart(system).inspect() == "CONFIRMED" and provider.store.commits == count


def test_revocation_after_pending_save_leaves_read_only_unknown_without_writing(system):
    pub, guide, discovery, setup, provider, native, kwargs, origin = system
    save = pub._save
    def revoke(state):
        save(state)
        if state["pending"]:
            origin.catalog["profiles"][0]["status"] = "REVOKED"
            origin.save()
    pub._save = revoke
    count = provider.store.commits
    with pytest.raises(InstructionError, match="RELEASE_WITHDRAWN"): pub.publish()
    resumed = restart(system)
    assert resumed.inspect() == "UNKNOWN" and provider.store.commits == count
    with pytest.raises(BallparkError, match="INSPECT_REQUIRED"): resumed.publish()


@pytest.mark.parametrize("failure", ["stage", "promote", "readback"])
def test_local_pending_save_failure_never_reaches_shared_write(system, failure):
    pub, guide, discovery, setup, provider, native, *_ = system
    promote = native.promote
    if failure == "readback":
        def lost():
            promote()
            native.failure = "readback"
        native.promote = lost
    else: native.failure = failure
    count = provider.store.commits
    with pytest.raises(SettingsError): pub.publish()
    assert provider.store.commits == count
    native.failure, native.promote = None, promote
    store = PrivateSettings(native)
    store.recover_pending()
    if failure == "readback":
        assert restart(system).inspect() == "UNKNOWN"


def test_cancel_allows_inspection_but_never_resends(system):
    pub, guide, discovery, setup, provider, *_ = system
    lose_reply(system)
    setup.cancel()
    count = provider.store.commits
    resumed = restart(system)
    assert resumed.inspect() == "CONFIRMED"
    assert resumed.setup.status()["state"] == "CANCELLED" and provider.store.commits == count


def test_next_revision_is_atomic_and_keeps_first_until_confirmed(system):
    pub, guide, discovery, setup, provider, *_ = system
    assert pub.publish() == "CONFIRMED"
    previous = copy.deepcopy(setup.private_choices()["descriptor"])
    guide.begin()
    confirm(guide)
    assert setup.private_choices()["descriptor"] == previous
    lose_reply(system)
    assert setup.private_choices()["descriptor"] == previous
    resumed = restart(system)
    assert resumed.inspect() == "CONFIRMED"
    assert resumed.setup.private_choices()["descriptor"]["revision"] == 2


@pytest.mark.parametrize("kind", ["wrong-root", "wrong-domain", "wrong-schema", "unpublished", "alias"])
def test_invalid_remote_binding_never_writes_or_activates(system, kind):
    pub, guide, discovery, setup, provider, *_ = system
    if kind == "wrong-root": discovery.port.root_id = "synthetic-wrong-root"
    elif kind == "wrong-domain": provider.store.document["domain_id"] = ACTORS[2]
    elif kind == "wrong-schema": provider.store.document["layout_version"] = 2
    elif kind == "unpublished": del provider.store.document["records"]["target.000.catalogue"]["body"]["discovery"]
    else: provider.store.document["records"]["target.000.catalogue"]["body"]["discovery"]["alias"] = "conflict"
    count = provider.store.commits
    with pytest.raises((SettingsError, BallparkError, AuthorityError, LayoutError)): pub.publish()
    assert provider.store.commits == count and setup.private_choices()["descriptor"] is None


@pytest.mark.parametrize("part", ["after", "before", "protected", "header"])
def test_persisted_plan_tamper_is_rejected_before_restart_inspection(system, part):
    pub, guide, discovery, setup, *_ = system
    lose_reply(system)
    value = copy.deepcopy(setup._payload)
    pending = value["ballpark_publication"]["pending"]
    plan = restored_plan(pending["plan"], None)
    from dataclasses import replace
    raw = json.loads(getattr(plan, part))
    if part == "after": raw["target.000.catalogue"]["body"]["enrollment"] = "ENROLLED"
    elif part == "before": raw["global.registry"]["generation"] = 3
    elif part == "protected": raw["global.commissioning"]["body"]["root_id"] = "wrong-root"
    else: raw["layout_revision"] = 2
    pending["plan"] = frozen_plan(replace(plan, **{part: encoded(raw)}))
    with pytest.raises(SettingsError): validated(value)


def test_discovery_refresh_preserves_descriptor_and_shared_decode(system):
    pub, guide, discovery, setup, provider, *_ = system
    assert pub.publish() == "CONFIRMED"
    before = shared(provider.store.document)
    discovery.clock = lambda: clock(221)
    discovery.observe((observation(observed_at=221),))
    discovery.publish()
    assert shared(provider.store.document) == before


def test_newer_remote_revision_does_not_confirm_or_overwrite_lost_old_write(system):
    pub, guide, discovery, setup, provider, *_ = system
    lose_reply(system)
    accepted = restart(system)
    assert accepted.inspect() == "CONFIRMED"
    accepted.guide.begin()
    confirm(accepted.guide)
    assert accepted.publish() == "CONFIRMED"
    # Use the original pre-confirmation private frame as a separate lost observer.
    from tests.security.test_private_settings import MemoryNative
    old_store = PrivateSettings(MemoryNative())
    old_store.save(copy.deepcopy(setup._payload), expected_revision=0)
    old_setup = Setup(old_store)
    older = Publisher(GuidedBallpark(old_setup, source=source(), runtime=FACTS),
                      Discovery(old_setup, **system[6]))
    count = provider.store.commits
    assert older.inspect() == "UNKNOWN" and provider.store.commits == count
    assert older.setup.private_choices()["descriptor"] is None


def test_native_protected_file_restart_confirmed_descriptor(tmp_path):
    # Actual native Windows/Linux protected filesystem, isolated synthetic profile.
    parent = tmp_path / "fresh-protected-parent"
    parent.mkdir(mode=0o700)
    if os.name == "nt":
        from tests.security.test_windows_key_native import protect
        from tb4.windows_key_native import WindowsKeyNative
        protect(WindowsKeyNative(), parent)
    root = parent / "synthetic-ballpark-profile"
    store = native_settings(root, create=True, owner_authorized=True)
    system = ready(store)
    pub = system[0]
    assert pub.publish() == "CONFIRMED"
    restored = Setup(native_settings(root))
    assert restored.private_choices()["descriptor"]["revision"] == 1
    assert restored._payload["ballpark_publication"]["active"] is not None
    assert not restored.status()["runtime_active"]


def test_remote_record_over_budget_cannot_be_replaced_or_reset(system):
    pub, guide, discovery, setup, provider, *_ = system
    provider.store.document["records"]["global.registry"] = dict(generation=0,
        operation_id="synthetic-oversized", retention="UNKNOWN", body={"unknown": "x"*4096})
    before = copy.deepcopy(provider.store.document)
    count = provider.store.commits
    with pytest.raises((SettingsError, AuthorityError, LayoutError)): pub.publish()
    assert provider.store.commits == count and provider.store.document == before
    assert setup.private_choices()["descriptor"] is None


def test_discovery_pending_plan_cannot_change_ballpark_selection(system):
    pub, guide, discovery, setup, provider, *_ = system
    assert pub.publish() == "CONFIRMED"
    discovery.clock = lambda: clock(221)
    discovery.observe((observation(source="NEIGHBOR_CACHE", observed_at=221),))
    # Force a legitimate discovery projection update from a newer shared probe.
    provider.store.document["records"]["target.000.catalogue"]["body"]["discovery"]["network"] = dict(
        value="ONLINE", source="NETWORK_PROBE", observed_at=100, valid_for_s=60, freshness="FRESH")
    save = discovery._save
    def interrupt(value):
        save(value)
        if value["pending"]: raise RuntimeError("synthetic before START")
    discovery._save = interrupt
    with pytest.raises(RuntimeError): discovery.publish()
    value = copy.deepcopy(setup._payload)
    plan = restored_plan(value["discovery"]["pending"]["plan"], None)
    after = json.loads(plan.after)
    after["target.000.catalogue"]["body"]["ballpark"][1] += 1
    from dataclasses import replace
    value["discovery"]["pending"]["plan"] = frozen_plan(replace(plan, after=encoded(after)))
    with pytest.raises(SettingsError): validated(value)
