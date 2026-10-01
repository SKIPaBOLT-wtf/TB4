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


def test_takeover_between_local_intent_and_write_keeps_pending_inspection(system):
    pub, guide, discovery, setup, provider, *_ = system
    save = pub._save
    def takeover(state):
        save(state)
        if state["pending"]:
            leader = Leadership(discovery.leader.backend, actor=ACTORS[1], enrollment={
                **ENROLLMENT, setup.installation_id: "synthetic-discoverer"})
            plan = leader.acquire(leader.observe(clock(340)), transition=tid("after-ballpark-intent"))
            assert leader.commit(plan, mode="START").outcome == "CONFIRMED"
    pub._save = takeover
    before = copy.deepcopy(provider.store.document["records"]["global.registry"])
    with pytest.raises(DiscoveryError, match="SUPERSEDED"): pub.publish()
    resumed = restart(system)
    count = provider.store.commits
    assert resumed.inspect() == "UNKNOWN" and provider.store.commits == count
    assert provider.store.document["records"]["global.registry"] == before


def test_all_64_slots_roundtrip_with_maximum_catalogue_fields_within_fixed_budgets(system):
    from dataclasses import replace, asdict
    from uuid import UUID
    from tb4.ballpark_publication import changes
    from tb4.commissioning_state import storage_spec
    from tb4.exchange_layout import Capacity, empty_document, slots, validate_document
    pub, guide, discovery, setup, provider, *_ = system
    choices = setup.private_choices()
    old_spec, _ = storage_spec(choices["storage"])
    spec = replace(old_spec, capacity=Capacity(64, 1, 1, 1))
    choices["storage"]["spec"] = asdict(spec)
    document = empty_document(spec.domain_id, spec.capacity)
    document["records"]["global.settings"] = dict(generation=0, operation_id=spec.setup_id,
        retention="RETAINED", body={"descriptor_state": "UNCONFIGURED"})
    document["records"]["global.commissioning"] = dict(generation=0, operation_id=spec.setup_id,
        retention="RETAINED", body=spec.marker("STORAGE_READY"))
    draft = copy.deepcopy(setup._payload["ballpark_draft"])
    template = draft["candidate"]["devices"][0]
    draft["candidate"]["devices"] = []
    for i in range(64):
        device = copy.deepcopy(template)
        device.update(device_id=str(UUID(int=i+1)), alias=f"target-{i:03d}" + "x"*22,
                      roles=["fetcher", "watchdog"], launch_mode={"fetcher": "DESKTOP_SESSION", "watchdog": "EXTERNAL"},
                      transports=["WOL", "SSH", "DRIVE_API", "SHARED_FOLDER"])
        device["display_name"] = device["alias"]
        draft["candidate"]["devices"].append(device)
        body = copy.deepcopy(provider.store.document["records"]["target.000.catalogue"]["body"])
        for kind in ("input", "output"):
            body["artifacts"][kind]["id"] = (kind + str(i)).ljust(128, "x")
        body["discovery"].update(device_id=device["device_id"], alias=device["alias"])
        body["discovery"]["network"] = dict(value="UNKNOWN", source="NETWORK_PROBE", observed_at=10**12,
                                            valid_for_s=86400, freshness="CLOCK_UNCERTAIN")
        document["records"][f"target.{i:03d}.catalogue"] = dict(generation=2**63-2, operation_id="e"*64,
                                                                 retention="RETAINED", body=body)
    validate_document(document)
    updates = changes(document, draft, choices)
    document["records"].update(updates)
    assert shared(document) == catalogue(draft["candidate"])
    for key, budget in slots(spec.capacity).items():
        assert len(encoded({key: document["records"][key]})) <= budget


@pytest.mark.parametrize("value", [None, [], [True, 1, [0], 0, 0, [0], []],
    [1, True, [0], 0, 0, [0], []], [1, 1, [0, 0], 0, 0, [0, 0], []],
    [1, 1, [0], -1, 0, [0], []], [1, 1, [0], 0, 0, [True], []],
    [1, 1, [0], 0, 0, [0], [0, 0]]], ids=["none", "empty", "bool-version", "bool-revision", "duplicate-role", "negative-os", "bool-launch", "duplicate-transport"])
def test_compact_codec_rejects_ambiguous_or_unrecognized_values(value):
    from tb4.ballpark_records import expand
    with pytest.raises(BallparkError): expand(value, {"device_id": ACTORS[0], "alias": "target"})


def qt_application():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def finish_dialog(app, dialog):
    import time
    deadline = time.monotonic() + 10
    while dialog.job is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert dialog.job is None


def test_real_qt_owner_review_approval_is_separate_from_publication(system):
    app = qt_application()
    from tb4.desktop.ballpark_dialog import BallparkDialog
    pub, guide, discovery, setup, provider, *_ = system
    # Start at partial local choices to exercise actual owner controls.
    payload = copy.deepcopy(setup._payload)
    payload["ballpark_draft"].update(candidate=None, decision=None)
    payload["ballpark_draft"]["proposal"]["devices"] = []
    setup._save(payload)
    dialog = BallparkDialog(pub)
    try:
        dialog.show()
        app.processEvents()
        assert len(dialog.rows) == 1 and not dialog.publish.isEnabled()
        _, selected, roles, *_ = dialog.rows[0]
        selected.setChecked(True)
        roles["fetcher"].setChecked(True)
        dialog.topology.setCurrentIndex(dialog.topology.findData("FLAT"))
        writes = provider.store.commits
        dialog.confirm.click()
        assert not dialog.confirm.isEnabled() and not dialog.publish.isEnabled()
        finish_dialog(app, dialog)
        assert dialog.publish.isEnabled() and setup.private_choices()["descriptor"] is None
        assert provider.store.commits == writes
        dialog.publish.click()
        finish_dialog(app, dialog)
        assert setup.private_choices()["descriptor"]["revision"] == 1
        assert provider.store.commits == writes+1
        assert "published" in dialog.message.text()
        assert not dialog.publish.isEnabled() and dialog.prepare.isEnabled()
    finally:
        finish_dialog(app, dialog)
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_real_qt_restart_unknown_exposes_only_inspection(system):
    app = qt_application()
    from tb4.desktop.ballpark_dialog import BallparkDialog
    lose_reply(system)
    pub = restart(system)
    dialog = BallparkDialog(pub)
    try:
        assert dialog.inspect.isEnabled()
        assert not any(b.isEnabled() for b in (dialog.prepare, dialog.confirm, dialog.publish))
        count = system[4].store.commits
        dialog.inspect.click()
        finish_dialog(app, dialog)
        assert pub.view(now=220)["status"] == "ACTIVE" and system[4].store.commits == count
    finally:
        finish_dialog(app, dialog)
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
