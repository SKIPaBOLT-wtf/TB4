"""Native checkpoint/guard stores in new owned Windows/Linux fixture roots."""
from contextlib import contextmanager
from dataclasses import replace
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import native_settings, SettingsError, MAX_BYTES
from tb4.reconfiguration_effects import Effects, SLOT, ledger
from tb4.watchdog.checkpoint_store import NativeCheckpoint, SCHEMA, SCHEMA_SHA256
from tb4.watchdog.leadership_runtime import Action, Receipt
from reconfiguration_controller_support import TRANSITION, resolution_archive
from reconfiguration_effects_support import guarded_system, runtime
from test_native_leadership import tid
from test_private_settings_native import fixture, protect_fixture  # noqa: F401

pytestmark = pytest.mark.skipif(sys.platform not in {"win32","linux"},reason="native Windows/Linux64")


def native_system(root, store):
    def private(name):
        return native_settings(root.parent/name,create=True,owner_authorized=True)
    return guarded_system(checkpoint_store=store,effect_store=private("effects"),
        profile_store=private("profile"),state_store=private("maintenance"),baseline_store=private("baseline"))


def test_actual_checkpoint_restart_reservation_cas_and_schema(fixture,capsys):
    from jsonschema import Draft202012Validator
    root,store = fixture; value = native_system(root,store)
    before = value.checkpoint.read()
    restarted = NativeCheckpoint(native_settings(root),installation_id=value.setup.installation_id,
        binding=value.flow.leader.backend.binding)
    assert restarted.read() == before
    assert restarted.reserve(TRANSITION,owner_authorized=True).maintenance == TRANSITION
    assert value.checkpoint.replace(before,before) is False
    assert value.checkpoint.read().maintenance == TRANSITION
    raw = (Path(__file__).parents[2]/SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SCHEMA_SHA256
    assert Draft202012Validator(json.loads(raw)).is_valid(store.read().payload)
    assert capsys.readouterr() == ("","")


def test_actual_all_native_maintenance_resolution_and_late_role_heartbeat(fixture):
    root,store = fixture; value = native_system(root,store)
    profile = value.setup.store.read()
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    decision,status = value.controller.proposal(); assert not status["requires_resolution"]
    archive = resolution_archive(value,native_settings(root.parent/"resolution",create=True,owner_authorized=True))
    assert value.controller.resolve(decision,archive,owner_authorized=True) == "RESOLVED"
    runner,sample,scheduled = runtime(value)
    runner.cycle()
    assert runner.state == "RUNNING" and runner.reason == "CONFIGURATION_MAINTENANCE"
    assert not scheduled and value.setup.store.read() == profile
    assert value.checkpoint.read().maintenance == TRANSITION
    assert value.controller.require_resolved(archive) == decision


def test_native_reservation_promotion_cut_recovers_exact_frame_without_authority_mutation(fixture):
    root,store = fixture; value = native_system(root,store)
    original = store.native.locked
    @contextmanager
    def stop():
        with original() as port:
            port.promote = lambda: (_ for _ in ()).throw(OSError("SYNTHETIC_RESERVATION_CUT"))
            yield port
    store.native.locked = stop
    commits = value.provider.store.commits
    with pytest.raises(ConfigurationError,match="INSPECT_REQUIRED"):
        value.controller.begin(owner_authorized=True)
    assert value.provider.store.commits == commits
    pending = (root/"settings.pending").read_bytes()
    store.native.locked = original
    with pytest.raises(ConfigurationError,match="OWNER_REQUIRED"):
        value.checkpoint.recover_pending()
    assert value.checkpoint.recover_pending(owner_authorized=True) == "INSPECT_REQUIRED"
    assert (root/"settings.json").read_bytes() == pending
    assert value.checkpoint.read().maintenance == TRANSITION
    assert value.provider.store.commits == commits


def test_native_effect_intent_cut_is_inspect_only_and_never_resends(fixture):
    root,store = fixture; value = native_system(root,store)
    effects = value.effects; original = effects.store.native.locked
    @contextmanager
    def stop():
        with original() as port:
            port.promote = lambda: (_ for _ in ()).throw(OSError("SYNTHETIC_EFFECT_CUT"))
            yield port
    effects.store.native.locked = stop
    commits = value.provider.store.commits
    with pytest.raises((ConfigurationError,SettingsError)):
        effects.ensure(value.checkpoint.read())
    effects.store.native.locked = original
    pending = (root.parent/"effects"/"settings.pending").read_bytes()
    assert effects.recover_local(owner_authorized=True) == "INSPECT_REQUIRED"
    assert (root.parent/"effects"/"settings.json").read_bytes() == pending
    assert effects.inspect() == "UNKNOWN"
    with pytest.raises(ConfigurationError,match="INSPECT_REQUIRED"):
        effects.ensure(value.checkpoint.read())
    assert value.provider.store.commits == commits and ledger(value.provider.store.document["records"][SLOT]) is None


def test_native_copy_and_broad_checkpoint_cannot_admit_or_resolve(fixture):
    root,store = fixture; value = native_system(root,store)
    foreign = root.parent/"copied-checkpoint"
    copied = native_settings(foreign,create=True,owner_authorized=True)
    path = foreign/"settings.json"; path.write_bytes((root/"settings.json").read_bytes()); protect_fixture(path)
    with pytest.raises((ConfigurationError,SettingsError)):
        NativeCheckpoint(copied,installation_id=value.setup.installation_id,binding=value.flow.leader.backend.binding)
    commits = value.provider.store.commits
    protect_fixture(root,broad=True)
    try:
        with pytest.raises(ConfigurationError,match="UNAVAILABLE"):
            value.controller.begin(owner_authorized=True)
    finally:
        protect_fixture(root)
    assert value.provider.store.commits == commits


@pytest.mark.parametrize("fault",["boolean-epoch","foreign-field","foreign-authority"])
def test_native_typed_checkpoint_refuses_malformed_saved_values(fixture,fault):
    root,store = fixture; value = native_system(root,store)
    snap = store.read(); payload = copy.deepcopy(snap.payload)
    if fault == "boolean-epoch":
        payload["checkpoint"]["grant"]["epoch"] = True
    elif fault == "foreign-field":
        payload["checkpoint"]["unknown"] = "SYNTHETIC_PRIVATE_CANARY"
    else:
        payload["authority"]["domain_id"] = "99999999-9999-4999-8999-999999999999"
    store.save(payload,expected_revision=snap.revision)
    with pytest.raises(ConfigurationError,match="NATIVE_CHECKPOINT"):
        value.checkpoint.read()


def test_native_full_action_unknown_capacity_preserves_every_reference(fixture):
    root,store = fixture; value = native_system(root,store)
    state = value.checkpoint.read()
    receipts = tuple(Receipt(a,tid(a.value),state.grant.epoch,"UNKNOWN") for a in Action)
    assert value.checkpoint.replace(state,replace(state,receipts=receipts))
    assert value.controller.begin(owner_authorized=True) == "MAINTENANCE"
    effects = ledger(value.provider.store.document["records"][SLOT])
    assert len(effects["entries"]) == len(Action)
    assert {e["operation_id"] for e in effects["entries"].values()} == {r.operation_id for r in receipts}
    decision,status = value.controller.proposal()
    assert status["counts"]["SHARED_EFFECT_UNKNOWN"] == len(Action)
    assert status["counts"]["LOCAL_EFFECT_UNKNOWN"] == len(Action)
    assert all(len(p.read_bytes()) <= MAX_BYTES for p in root.parent.rglob("settings.json"))
