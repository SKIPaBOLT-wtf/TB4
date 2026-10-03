"""One shared root destination and exact partial facts, never first-run READY."""
import copy
from dataclasses import replace
import json
import pytest

from tb4.commissioning_checks import CommissionedStorage
from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError,WriteResult
from tb4.exchange_layout import Capacity,encoded
from tb4.private_settings import SettingsError
from tb4.reconfiguration_root_facts import PartialRootInspection
from tb4.reconfiguration_root_plan import root_plan,references,matches_plan
from tb4.reconfiguration_roots import DocsRootMoves,RootContext
from tb4.reconfiguration_root_settlement import InheritedRootSettlement
from tb4.watchdog.leadership_runtime import Action
from reconfiguration_candidate_support import private
from reconfiguration_roots_support import system,TARGET
from test_reconfiguration_effects import acquire_fallback
from test_reconfiguration_roots import updates


def test_actual_original_native_plan_and_exact_shared_witness_precede_any_sdk_move():
    s = system(); before = copy.deepcopy(s.value.provider.store.document); profile = s.value.setup.store.read()
    assert s.roots.begin(owner_authorized=True) == "MOVING" and not updates(s)
    state = s.context.store.read().payload
    doc = s.value.provider.store.document; plan = doc["records"]["global.summary"]["body"]["tb4_effects_v1"]["root_plan"]
    assert root_plan(plan) == plan and plan["target_root"] == TARGET and plan["transition_id"] == state["transition_id"]
    assert matches_plan(doc,s.value.context.leadership.backend.binding,plan)
    assert {k for k,v in before["records"].items() if doc["records"][k] != v} == {"global.summary"}
    assert s.value.setup.store.read() == profile
    assert s.roots.advance(owner_authorized=True) == "CONFIRMED" and len(updates(s)) == 1


def test_second_different_root_plan_is_refused_before_native_plan_or_sdk_without_overwriting_first():
    s = system(); s.roots.begin(owner_authorized=True); other = "synthetic-unplanned-root"
    s.value.provider.metadata[other] = copy.deepcopy(s.value.provider.metadata[TARGET])
    s.value.provider.metadata[other]["id"] = other
    store = private(29); roots = DocsRootMoves(RootContext(s.candidate,s.checker,store,other))
    before = copy.deepcopy(s.value.provider.store.document)
    with pytest.raises(ConfigurationError,match="ROOT_PLAN_CHANGED"):
        roots.begin(owner_authorized=True)
    assert store.read() is None and s.value.provider.store.document == before and not updates(s)


@pytest.mark.parametrize("applied",[False,True])
def test_lost_plan_receipt_inspects_exact_same_intent_and_never_reissues_unknown(applied):
    s = system(); compare = s.value.context.leadership.backend.compare_replace; calls = []
    def lost(snapshot,desired):
        calls.append(True)
        if applied:
            compare(snapshot,desired)
        return WriteResult.UNKNOWN
    s.value.context.leadership.backend.compare_replace = lost
    assert s.roots.begin(owner_authorized=True) == ("MOVING" if applied else "UNKNOWN")
    assert calls == [True] and not updates(s)
    s.value.context.leadership.backend.compare_replace = compare
    if applied:
        assert s.roots.advance(owner_authorized=True) == "CONFIRMED" and len(updates(s)) == 1
    else:
        assert s.roots.advance(owner_authorized=True) == "UNKNOWN" and calls == [True] and not updates(s)
        assert "root_plan" not in s.value.provider.store.document["records"]["global.summary"]["body"]["tb4_effects_v1"]


@pytest.mark.parametrize("moved",[0,1,3])
def test_new_current_role_inspects_exact_partial_plan_with_old_private_stores_unavailable_and_no_ready(moved):
    s = system(); s.roots.begin(owner_authorized=True)
    for _ in range(moved):
        assert s.roots.advance(owner_authorized=True) in {"CONFIRMED","MOVED"}
    context = acquire_fallback(s.value)[2]; inspector = PartialRootInspection(context)
    before = copy.deepcopy(s.value.provider.store.document); requests = len(updates(s)); profile = context.setup.store.read()
    def absent():
        raise SettingsError("SYNTHETIC_OLD_HOST_UNAVAILABLE")
    for store in (s.value.setup.store,s.context.store,s.value.context.store,s.value.context.baseline.store,
                  s.value.context.checkpoint.store,s.value.context.effects.store,
                  s.context.candidate.context.profile,s.context.candidate.context.archive,
                  s.context.candidate.context.transaction,s.context.candidate.context.resolution.store):
        store.read = absent
    proof = inspector.inspect()
    assert proof.public_summary() == dict(schema_version=1,moved=moved,remaining=3-moved,
        requires_resolution=False,execution_authorized=False)
    assert inspector.require_fresh(proof).objects == proof.objects
    assert proof.epoch == 2 and len(json.loads(proof.objects)) == 3
    if moved:
        with pytest.raises(SettingsError,match="STORAGE_UNAVAILABLE"):
            CommissionedStorage(context.storage_port).verify(context.setup.private_choices()["storage"])
    assert s.value.provider.store.document == before and len(updates(s)) == requests and context.setup.store.read() == profile
    assert len([m for m in s.value.provider.metadata.values() if m.get("mimeType") == "application/vnd.google-apps.document"]) == 1


def test_inherited_unknown_is_a_blocker_until_exact_after_receipt_settles_and_saved_facts_expire():
    from test_reconfiguration_root_settlement import inherited
    s,ctx,settlement = inherited(); inspector = PartialRootInspection(ctx)
    before = copy.deepcopy(s.value.provider.store.document); count = len(updates(s))
    proof = inspector.inspect(); assert proof.public_summary()["requires_resolution"]
    assert s.value.provider.store.document == before and len(updates(s)) == count
    assert settlement.settle(settlement.inspect(),owner_authorized=True) == "CONFIRMED"
    with pytest.raises(ConfigurationError,match="ROOT_CHANGED"):
        inspector.require_fresh(proof)
    assert not inspector.inspect().public_summary()["requires_resolution"] and len(updates(s)) == count


@pytest.mark.parametrize("fault",["target","source-root","blueprint","references","fingerprint","metadata-parent","metadata-witness","catalogue","work","missing","source","force","clock","action","old-witness"])
def test_wrong_shared_plan_metadata_work_role_or_profile_never_grants_partial_routing(fault):
    s = system(); s.roots.begin(owner_authorized=True); ctx = s.value.context
    doc = s.value.provider.store.document; plan = doc["records"]["global.summary"]["body"]["tb4_effects_v1"]["root_plan"]
    ref = s.context.store.read().payload["objects"][0]["id"]
    if fault == "target":
        plan["target_root"] = "synthetic-missing-root"
    elif fault == "source-root":
        plan["source_root"] = "synthetic-wrong-original-root"
    elif fault in {"blueprint","references","fingerprint"}:
        plan[{"blueprint":"blueprint_sha256","references":"references_sha256","fingerprint":"records_sha256"}[fault]] = "a"*64
    elif fault == "metadata-parent":
        s.value.provider.metadata[ref]["parents"] = ["synthetic-unplanned-root"]
    elif fault == "metadata-witness":
        assert s.roots.advance(owner_authorized=True) == "CONFIRMED"
        s.value.provider.metadata[ref]["properties"]["tb4Reconfiguration"] = "a"*64
    elif fault == "catalogue":
        doc["records"]["target.000.catalogue"]["body"]["artifacts"]["input"]["id"] = "synthetic-unbound-id"
    elif fault == "work":
        doc["records"]["target.000.work"].update(generation=12,operation_id="a"*64,retention="UNREAD",body={"synthetic":True})
    elif fault == "missing":
        del s.value.provider.metadata[ref]
    elif fault == "source":
        ctx.source.catalog["profiles"][0]["status"] = "REVOKED"; ctx.source.save()
    elif fault == "force":
        doc["records"]["global.force_request"].update(retention="BUSY",body={"synthetic":True})
    elif fault == "clock":
        from test_native_leadership import clock
        ctx = replace(ctx,clock=lambda:clock(trusted=False))
    elif fault == "action":
        caps = ctx.capabilities(); ctx = replace(ctx,capabilities=lambda:replace(caps,actions=frozenset({Action.SCAN})))
    else:
        payload = copy.deepcopy(ctx.setup._payload); payload["choices"]["storage"]["root_transition"] = "a"*64
        ctx.setup.store.save(payload,expected_revision=ctx.setup.snapshot.revision)
    before = copy.deepcopy(doc); requests = len(updates(s))
    with pytest.raises((AuthorityError,SettingsError)):
        PartialRootInspection(ctx).inspect()
    assert s.value.provider.store.document == before and len(updates(s)) == requests


def test_forged_or_other_inspector_partial_facts_cannot_be_a_resume_grant():
    s = system(); s.roots.begin(owner_authorized=True); inspector = PartialRootInspection(s.value.context); proof = inspector.inspect()
    before = copy.deepcopy(s.value.provider.store.document)
    with pytest.raises(ConfigurationError):
        inspector.require_fresh(replace(proof,target_root="synthetic-unplanned"))
    with pytest.raises(ConfigurationError):
        PartialRootInspection(s.value.context).require_fresh(proof)
    assert s.value.provider.store.document == before and not updates(s)


def test_actual_max_capacity129_fixed_objects_keep_existing_shared_private_budgets():
    s = system(capacity=Capacity(64,16,128,32)); s.roots.begin(owner_authorized=True)
    proof = PartialRootInspection(s.value.context).inspect()
    assert proof.public_summary()["remaining"] == 129 and len(json.loads(proof.objects)) == 129
    value = s.value.provider.store.document["records"]["global.summary"]["body"]["tb4_effects_v1"]
    assert len(encoded(value)) <= 6144 and len(encoded(s.context.store.read().payload)) <= 128*1024
    assert not updates(s)
