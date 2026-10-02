"""Root metadata-only identity, UNKNOWN/no resend and stale-role boundaries."""
import copy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import pytest

from tb4.commissioning_checks import CommissionedStorage
from tb4.commissioning_state import storage_spec
from tb4.configuration_contract import ConfigurationError, configuration
from tb4.drive.commissioning import Allocation
from tb4.drive.commissioning_bootstrap import AuthorityHandle
from tb4.private_settings import SettingsError
from tb4.reconfiguration_roots import DocsRootMoves, SCHEMA, SCHEMA_SHA256
from tb4.watchdog.leadership_runtime import Action
from reconfiguration_roots_support import system, TARGET
from test_reconfiguration_effects import acquire_fallback


def updates(s):
    return [kw for method,kw in s.value.provider.calls if method == "files.update"]


def test_existing_objects_move_once_and_original_profile_work_and_media_are_preserved(capsys):
    s = system(); v = s.value
    profile = v.setup.store.read(); document = copy.deepcopy(v.provider.store.document)
    objects = copy.deepcopy(v.provider.created); media = copy.deepcopy(s.media)
    assert s.roots.begin(owner_authorized=True) == "MOVING"
    assert not s.moves
    assert [s.roots.advance(owner_authorized=True) for _ in range(3)] == ["CONFIRMED","CONFIRMED","MOVED"]
    facts = s.roots.verify_moved()
    assert len(facts) == len(s.moves) == len(updates(s)) == 3
    assert len(set(s.moves)) == 3 and v.provider.created == objects and s.media == media
    assert {k:r for k,r in v.provider.store.document["records"].items() if k != "global.summary"} == {
        k:r for k,r in document["records"].items() if k != "global.summary"}
    assert v.setup.store.read() == profile
    assert configuration(v.provider.store.document)["phase"] == "MAINTENANCE"
    assert len([x for x in v.provider.metadata.values() if x.get("mimeType") == "application/vnd.google-apps.document"]) == 1
    assert all(set(k["body"]) == {"properties"} and "uploadType" not in k for k in updates(s))
    assert s.roots.advance(owner_authorized=True) == "MOVED" and len(updates(s)) == 3
    assert capsys.readouterr() == ("","")


def test_unique_metadata_witness_and_seals_are_actual_but_not_yet_an_active_root():
    s = system(); s.roots.begin(owner_authorized=True)
    for _ in range(3):
        s.roots.advance(owner_authorized=True)
    facts = s.roots.verify_moved()
    for item in facts:
        value = s.value.provider.metadata[item["id"]]
        assert value["parents"] == [TARGET]
        assert value["properties"] == s.roots.new._props(item["key"],s.roots.new.spec.operation(item["key"]))
        assert "tb4Reconfiguration" in value["properties"]
        if item["key"] != "authority":
            allocated = Allocation(item["id"],s.roots.new.spec.operation(item["key"]),seal=item["after_seal"])
            assert s.roots.new.inspect(item["key"],allocated) == allocated
    # Actual first-run still refuses until the separate same-authority remote rebind.
    last = facts[-1]
    _,old = storage_spec(s.value.setup.private_choices()["storage"])
    record = dict(spec=asdict(s.roots.new.spec),
        authority=AuthorityHandle(last["id"],last["after_seal"],old.tab_id).record(),
        root_transition=s.value.context.baseline.transition_id)
    with pytest.raises(SettingsError,match="STORAGE_UNAVAILABLE"):
        CommissionedStorage(s.roots.new).verify(record)


@pytest.mark.parametrize("failure",["before","after"])
def test_response_loss_inspects_same_item_and_never_reissues_move(failure):
    s = system(); s.roots.begin(owner_authorized=True)
    s.failure[0] = failure
    assert s.roots.advance(owner_authorized=True) == "UNKNOWN"
    requests = len(updates(s)); original = s.value.setup.store.read()
    restarted = DocsRootMoves(s.context)
    expected = "UNKNOWN" if failure == "before" else "CONFIRMED"
    assert restarted.inspect() == expected
    assert len(updates(s)) == requests == 1
    assert s.value.setup.store.read() == original
    if failure == "before":
        assert restarted.advance(owner_authorized=True) == "UNKNOWN"
        assert s.value.effects.receipt(Action.IDENTITY)["outcome"] == "UNKNOWN"
    else:
        assert s.value.effects.receipt(Action.IDENTITY)["outcome"] == "COMPLETE"


def test_native_and_shared_intent_are_present_and_exclusive_during_sdk_send():
    s = system(); s.roots.begin(owner_authorized=True)
    seen = []
    def inspect_before():
        # The sending live call holds the actual local native lock.
        with pytest.raises(SettingsError,match="BUSY"):
            s.context.store.read()
        assert s.value.effects.receipt(Action.IDENTITY)["outcome"] == "UNKNOWN"
        seen.append(True)
    s.before[0] = inspect_before
    assert s.roots.advance(owner_authorized=True) == "CONFIRMED" and seen == [True]


@pytest.mark.parametrize("at",["before-send","during-send"])
def test_first_cas_stale_fallback_needs_no_ack_and_old_root_sender_stops(at):
    s = system(); s.roots.begin(owner_authorized=True)
    original = s.value.setup.store.read(); taken = []
    def take():
        taken.append(acquire_fallback(s.value))
    if at == "before-send":
        start = s.value.effects.start
        def start_and_take(*args):
            result = start(*args); take(); return result
        s.value.effects.start = start_and_take
        with pytest.raises(ConfigurationError,match="OWNER_SUPERSEDED"):
            s.roots.advance(owner_authorized=True)
        assert not updates(s)
    else:
        s.before[0] = take
        assert s.roots.advance(owner_authorized=True) == "APPLIED_OWNER_SUPERSEDED"
        assert len(updates(s)) == 1
    assert taken[0][2].checkpoint.read().grant.epoch == 2
    assert s.roots.inspect() == ("UNKNOWN" if at == "before-send" else "APPLIED_OWNER_SUPERSEDED")
    assert s.value.effects.receipt(Action.IDENTITY)["outcome"] == "UNKNOWN"
    assert s.value.setup.store.read() == original
    assert len([m for m in s.value.provider.metadata.values() if m.get("mimeType") == "application/vnd.google-apps.document"]) == 1


@pytest.mark.parametrize("fault",["target-access","withdrawn","unread","action","clock"])
def test_failed_current_prerequisite_sends_no_sdk_move(fault):
    s = system(); original = s.value.setup.store.read()
    if fault == "target-access":
        s.value.provider.metadata[TARGET]["capabilities"]["canEdit"] = False
    elif fault == "withdrawn":
        s.value.source.catalog["profiles"][0]["status"] = "REVOKED"; s.value.source.save()
    elif fault == "unread":
        s.value.provider.store.document["records"]["target.000.work"].update(
            generation=7,operation_id="e"*64,retention="UNREAD",body={"private":"SYNTHETIC_CANARY"})
    elif fault == "action":
        s.value.caps[0] = replace(s.value.caps[0],actions=frozenset({Action.SCAN}))
    else:
        from test_native_leadership import clock
        s.value.context = replace(s.value.context,clock=lambda:clock(trusted=False))
        s.value.controller.context = s.value.context
        s.roots.ctx = s.value.context
    with pytest.raises((ConfigurationError,SettingsError)):
        s.roots.begin(owner_authorized=True)
    assert not updates(s) and s.value.setup.store.read() == original


def test_foreign_object_or_record_hash_cannot_be_injected_into_saved_move_plan():
    for fault in ("object","hash"):
        s = system(); s.roots.begin(owner_authorized=True)
        snap = s.context.store.read(); changed = copy.deepcopy(snap.payload)
        if fault == "object":
            changed["objects"][0]["id"] = "synthetic-foreign-object"
        else:
            changed["records_sha256"] = "0"*64
        s.context.store.save(changed,expected_revision=snap.revision)
        with pytest.raises(ConfigurationError,match="ROOT_WAL"):
            DocsRootMoves(s.context).advance(owner_authorized=True)
        assert not updates(s)


def test_wrong_historical_after_witness_never_resolves_unknown():
    s = system(); s.roots.begin(owner_authorized=True); s.failure[0] = "after"
    assert s.roots.advance(owner_authorized=True) == "UNKNOWN"
    item = s.context.store.read().payload["objects"][0]
    s.value.provider.metadata[item["id"]]["properties"]["tb4Reconfiguration"] = "0"*64
    assert DocsRootMoves(s.context).inspect() == "CONFLICT"
    assert len(updates(s)) == 1 and s.value.effects.receipt(Action.IDENTITY)["outcome"] == "UNKNOWN"


def test_root_schema_exact_pin_and_default_owner_refusal():
    from jsonschema import Draft202012Validator
    s = system()
    with pytest.raises(ConfigurationError,match="OWNER_REQUIRED"):
        s.roots.begin()
    assert s.context.store.read() is None and not updates(s)
    s.roots.begin(owner_authorized=True)
    raw = (Path(__file__).parents[2]/SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SCHEMA_SHA256
    assert Draft202012Validator(json.loads(raw)).is_valid(s.context.store.read().payload)
