from __future__ import annotations

import copy
import json

import pytest

from tests.development.test_ledger import SHA, accept, event, ledger, save, update
from tests.development.test_checkpoint import Remote, prepare, send, validate_plan
from tools.development.checkpoint import project
from tools.development.defects import (REGISTRY, migrate, open_repair,
                                        validate_registry_history)
from tools.development.ledger import JOURNAL, PLAN, RESUME, LedgerError, load, validate, validate_transitions

MANIFEST = PLAN + "/manifest.yaml"


def defect():
    return dict(title="Synthetic regression", status="OPEN", detected_in="RP-001.C1",
                suspected_origin=None, proven_origin=None,
                reproduction=dict(procedure="Exercise a deterministic synthetic regression",
                                  failing_source=SHA, passing_source=None, evidence=[]),
                repair_steps=["RP-001"], affected_acceptance=["RP-001.C1"], affected_requirements=["R19"],
                hypotheses=[dict(id="H001", claim="Synthetic first hypothesis", result="FAILED", evidence=[])],
                repairs=[], issue="https://github.com/SKIPaBOLT-wtf/TB4/issues/7", regression_test=None,
                resolution_evidence=[], notes="Synthetic only; issue is a reference, never read or mutated.", legacy_record=None)


@pytest.fixture
def accepted(ledger):
    accept(ledger)
    manifest = load(ledger, MANIFEST)
    for number in (2, 3):
        item = f"RP-{number:03d}"
        step = json.loads(json.dumps(manifest["steps"]["RP-001"]).replace("RP-001", item))
        step["depends_on"] = [f"RP-{number-1:03d}"]
        manifest["steps"][item] = step
        save(ledger, PLAN + f"/steps/{item}.md", "\n".join(f"- [x] **{item}.C{i}** - Fixture" for i in range(1, 5)))
        for path in step["evidence"]:
            old = path.replace(item, "RP-001")
            save(ledger, path, json.loads(json.dumps(load(ledger, old)).replace("RP-001", item)))
        rows = [json.loads(line.replace("RP-001", item)) for line in
                (ledger / JOURNAL / "RP-001/A001/events.jsonl").read_text().splitlines()]
        save(ledger, JOURNAL + f"/{item}/A001/events.jsonl", rows)
    save(ledger, MANIFEST, manifest)
    save(ledger, PLAN + "/CHECKLIST.md", "\n".join(f"- [x] [{i} - Fixture](steps/{i}.md)" for i in manifest["steps"]))
    save(ledger, PLAN + "/requirements.yaml", {"requirements": {"R19": {"steps": list(manifest["steps"])}}})
    save(ledger, REGISTRY, {"schema_version": 2, "defects": {"DEF-001": defect()}})
    assert validate(ledger, reachable=lambda _: True)["verified"] == 3
    return ledger


def repair(root):
    return open_repair(load(root, MANIFEST), load(root, REGISTRY), "DEF-001", "RP-001", "RP-001-A002-0001")


def repair_event(n=1, kind="INTENT", item="RP-001"):
    row = event(n, kind, None if kind == "INTENT" else "RP-001-A002-0001", "PENDING" if kind == "INTENT" else "PASS")
    row = json.loads(json.dumps(row).replace("A001", "A002").replace("RP-001", item))
    row["action_id"] = "REPAIR-REGRESSION"
    return row


def apply(root, plan):
    for path, content in plan.files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def start_repair(root):
    manifest, registry = repair(root)
    plan = prepare(root, repair_event(), "work/repair", SHA, manifest=manifest, defects=registry, reachable=lambda _: True)
    validate_plan(root, plan, reachable=lambda _: True)
    apply(root, plan)
    return plan


def test_repair_snapshot_and_transitive_hold_preserve_failed_hypotheses(accepted):
    old = load(accepted, MANIFEST)
    manifest, registry = repair(accepted)
    validate_transitions(old, manifest)
    for item, step in manifest["steps"].items():
        assert step["active_attempt"] == "A002" and not step["completed_checks"]
        assert step["acceptance_history"][0]["check_evidence"] == old["steps"][item]["check_evidence"]
        assert step["evidence"] == old["steps"][item]["evidence"]
        assert len(step["revalidation_required"]) == 4
        assert step["status"] == ("IN_PROGRESS" if item == "RP-001" else "BLOCKED")
    assert registry["defects"]["DEF-001"]["hypotheses"][0]["result"] == "FAILED"
    assert load(accepted, MANIFEST) == old  # Pure candidate; no local mutation.


def test_synthetic_intent_outcome_evidence_and_reacceptance_use_checkpoint(accepted, tmp_path):
    manifest, registry = repair(accepted)
    plan = prepare(accepted, repair_event(), "work/repair", SHA, manifest=manifest, defects=registry, reachable=lambda _: True)
    remote = Remote()
    assert send(accepted, plan, remote, tmp_path / "repair-pending.json")["state"] == "VERIFIED"
    assert remote.files == plan.files and remote.writes == 1
    apply(accepted, plan)
    assert validate(accepted, reachable=lambda _: True)["verified"] == 0
    # Simulated outcomes are explicitly fixture-only, not actual product repairs.
    for item in ("RP-001", "RP-002", "RP-003"):
        manifest = load(accepted, MANIFEST)
        manifest["current_step"] = item
        step = manifest["steps"][item]
        if item != "RP-001":
            step["status"] = "IN_PROGRESS"
            apply(accepted, prepare(accepted, repair_event(item=item), "work/repair", SHA,
                  manifest=manifest, reachable=lambda _: True))
        evidence = {}
        for i in range(1, 5):
            old = PLAN + f"/evidence/{item}/A001/C{i}.json"
            receipt = json.loads(json.dumps(load(accepted, old)).replace("A001", "A002"))
            path = old.replace("A001", "A002")
            evidence[path] = json.dumps(receipt)
            step["completed_checks"].append(f"{item}.C{i}")
            step["check_evidence"][f"{item}.C{i}"] = [path]
            step["evidence"].append(path)
        step.update(status="VERIFIED", revalidation_required=[])
        result = prepare(accepted, repair_event(2, "OUTCOME", item), "work/repair", SHA,
                         manifest=manifest, evidence=evidence, reachable=lambda _: True)
        validate_plan(accepted, result, reachable=lambda _: True)
        apply(accepted, result)
    assert validate(accepted, reachable=lambda _: True)["verified"] == 3
    assert load(accepted, REGISTRY)["defects"]["DEF-001"]["status"] == "OPEN"


def test_issue_closure_alone_cannot_resolve_or_remove_hold(accepted):
    start_repair(accepted)
    update(accepted, REGISTRY, lambda r: r["defects"]["DEF-001"].update(status="RESOLVED", notes="Issue marked closed"))
    with pytest.raises(LedgerError, match="DEFECT_RESOLUTION_UNPROVEN"):
        validate(accepted, reachable=lambda _: True)


def test_clearing_rechecks_without_acceptance_is_rejected(accepted):
    start_repair(accepted)
    update(accepted, MANIFEST, lambda m: m["steps"]["RP-003"].update(revalidation_required=[]))
    with pytest.raises(LedgerError, match="REPAIR_HOLD_REMOVED"):
        validate(accepted, reachable=lambda _: True)


def test_old_build_cannot_restore_acceptance(accepted):
    old = load(accepted, MANIFEST)
    start_repair(accepted)
    manifest = load(accepted, MANIFEST)
    manifest["steps"]["RP-003"] = old["steps"]["RP-003"]
    save(accepted, MANIFEST, manifest)
    for path, content in project(accepted, manifest).items():
        (accepted / path).write_text(content)
    with pytest.raises(LedgerError, match="DEPENDENCY_NOT_VERIFIED|REPAIR_ACCEPTANCE_STALE"):
        validate(accepted, reachable=lambda _: True)


def test_unknown_culprit_is_valid_but_unproven_origin_is_not(accepted):
    assert load(accepted, REGISTRY)["defects"]["DEF-001"]["proven_origin"] is None
    update(accepted, REGISTRY, lambda r: r["defects"]["DEF-001"].update(
        proven_origin=dict(work_item="RP-001", source_ref=SHA, evidence=[])))
    with pytest.raises(LedgerError, match="DEFECT_ORIGIN_UNPROVEN"):
        validate(accepted, reachable=lambda _: True)


@pytest.mark.parametrize("field", ["hypotheses", "repairs"])
def test_failed_hypotheses_and_repair_links_cannot_be_erased(accepted, field):
    manifest, registry = repair(accepted)
    changed = copy.deepcopy(registry)
    changed["defects"]["DEF-001"][field] = []
    with pytest.raises(LedgerError, match="DEFECT_HISTORY_REWRITTEN"):
        validate_registry_history(registry, changed, manifest)


def test_acceptance_snapshot_cannot_be_erased(accepted):
    old = load(accepted, MANIFEST)
    manifest, _ = repair(accepted)
    manifest["steps"]["RP-001"]["acceptance_history"] = []
    with pytest.raises(LedgerError, match="ACCEPTANCE_SNAPSHOT_MISSING"):
        validate_transitions(old, manifest)


def test_planned_dependents_stay_unstarted_and_concurrent_work_blocks_takeover(accepted):
    manifest = load(accepted, MANIFEST)
    manifest["steps"]["RP-003"].update(status="PLANNED", active_attempt=None, completed_checks=[], check_evidence={}, evidence=[])
    changed, _ = open_repair(manifest, load(accepted, REGISTRY), "DEF-001", "RP-001", "RP-001-A002-0001")
    assert changed["steps"]["RP-003"] == manifest["steps"]["RP-003"]
    manifest["steps"]["RP-002"]["status"] = "IN_PROGRESS"
    with pytest.raises(LedgerError, match="REPAIR_CONCURRENT_WORK_REQUIRES_RECONCILIATION"):
        open_repair(manifest, load(accepted, REGISTRY), "DEF-001", "RP-001", "RP-001-A002-0001")


def test_lossless_migration_keeps_historical_symptoms_open(accepted):
    previous = dict(title="Historical symptom", status="OPEN", detected_in="IP-68",
                    suspected_origin=None, proven_origin=None, reproduction_step="RP-001",
                    repair_steps=["RP-001"], required_acceptance=["RP-003"], rule="Manual recovery does not close it.")
    old = dict(schema_version=1, defects={"DEF-001": previous, "DEF-002": previous})
    current = migrate(old, load(accepted, MANIFEST))
    validate_registry_history(old, current, load(accepted, MANIFEST))
    for record in current["defects"].values():
        assert record["status"] == "OPEN" and record["proven_origin"] is None
        assert record["reproduction"]["passing_source"] is None
        assert json.loads(record["legacy_record"]) == previous


def test_no_raw_provider_or_private_fields(accepted):
    update(accepted, REGISTRY, lambda r: r["defects"]["DEF-001"].update(raw_provider="canary"))
    with pytest.raises(LedgerError, match="RECORD_SCHEMA_INVALID"):
        validate(accepted, reachable=lambda _: True)


def test_new_repair_cannot_omit_transitive_rechecks(accepted):
    old_manifest, old_registry = load(accepted, MANIFEST), load(accepted, REGISTRY)
    manifest, registry = repair(accepted)
    del registry["defects"]["DEF-001"]["repairs"][0]["rechecks"]["RP-003"]
    with pytest.raises(LedgerError, match="REPAIR_IMPACT_INCOMPLETE"):
        validate_registry_history(old_registry, registry, old_manifest, manifest)
    with pytest.raises(LedgerError, match="REPAIR_IMPACT_INCOMPLETE"):
        prepare(accepted, repair_event(), "work/repair", SHA, manifest=manifest, defects=registry, reachable=lambda _: True)


def test_serialized_repair_cannot_bypass_impact_review(accepted):
    manifest, registry = repair(accepted)
    plan = prepare(accepted, repair_event(), "work/repair", SHA, manifest=manifest, defects=registry, reachable=lambda _: True)
    del registry["defects"]["DEF-001"]["repairs"][0]["rechecks"]["RP-003"]
    plan.files[REGISTRY] = json.dumps(registry)
    with pytest.raises(LedgerError, match="REPAIR_IMPACT_INCOMPLETE"):
        validate_plan(accepted, plan, reachable=lambda _: True)


def test_new_defect_cannot_claim_legacy_resolution_exemption(accepted):
    before = load(accepted, REGISTRY)
    after = copy.deepcopy(before)
    after["defects"]["DEF-002"] = defect()
    after["defects"]["DEF-002"].update(status="RESOLVED", legacy_record='{"invented":"history"}')
    with pytest.raises(LedgerError, match="DEFECT_LEGACY_EXEMPTION_FORGED"):
        validate_registry_history(before, after, load(accepted, MANIFEST))


def test_repair_rechecks_must_cover_defined_checks(accepted):
    start_repair(accepted)
    update(accepted, REGISTRY, lambda r: r["defects"]["DEF-001"]["repairs"][0]["rechecks"]["RP-003"].update(checks=["RP-003.C1"]))
    with pytest.raises(LedgerError, match="REPAIR_RECHECK_INCOMPLETE"):
        validate(accepted, reachable=lambda _: True)


def repeated_defect_history(accepted):
    old_manifest, old_registry = load(accepted, MANIFEST), load(accepted, REGISTRY)
    manifest, registry = repair(accepted)
    later = copy.deepcopy(registry['defects']['DEF-001'])
    later['repairs'] = [dict(item='RP-001',attempt='A002',intent_event='RP-001-A002-0005',
                           rechecks={'RP-001':dict(attempt='A002',checks=[f'RP-001.C{i}' for i in range(1,5)])})]
    registry['defects']['DEF-002'] = later
    return old_manifest, old_registry, manifest, registry


def test_later_defect_in_reopened_attempt_preserves_single_acceptance_snapshot(accepted):
    old_manifest, old_registry, manifest, registry = repeated_defect_history(accepted)
    # Dictionary order does not determine journal chronology.
    registry['defects'] = dict(reversed(list(registry['defects'].items())))
    before = copy.deepcopy(manifest)
    validate_registry_history(old_registry, registry, old_manifest, manifest)
    assert manifest == before and len(manifest['steps']['RP-001']['acceptance_history']) == 1


@pytest.mark.parametrize('case',['missing-opening','missing-snapshot','different-attempt','same-intent','dependent'])
def test_later_defect_cannot_bypass_reopening_or_impact(accepted,case):
    old_manifest, old_registry, manifest, registry = repeated_defect_history(accepted)
    later=registry['defects']['DEF-002']['repairs'][0]
    if case=='missing-opening':registry['defects']['DEF-001']['repairs']=[]
    elif case=='missing-snapshot':manifest['steps']['RP-001']['acceptance_history']=[]
    elif case=='different-attempt':later.update(attempt='A003',intent_event='RP-001-A003-0001')
    elif case=='same-intent':later['intent_event']='RP-001-A002-0001'
    elif case=='dependent':later['rechecks']['RP-002']=copy.deepcopy(later['rechecks']['RP-001'])
    with pytest.raises(LedgerError):validate_registry_history(old_registry,registry,old_manifest,manifest)


def reopen_after_old_resolution(root):
    manifest=load(root,MANIFEST);registry=load(root,REGISTRY)
    old=registry['defects']['DEF-001']
    old.update(status='RESOLVED',regression_test='tests/synthetic.py',
        resolution_evidence=[PLAN+'/evidence/RP-001/A001/C1.json'],
        repairs=[dict(item='RP-001',attempt='A001',intent_event='RP-001-A001-0001',
                      rechecks={'RP-001':dict(attempt='A001',checks=manifest['steps']['RP-001']['completed_checks'])})])
    old['reproduction']['passing_source']=SHA
    registry['defects']['DEF-002']=defect()
    save(root,REGISTRY,registry)
    assert validate(root,reachable=lambda _:True)['verified']==3
    manifest,registry=open_repair(manifest,registry,'DEF-002','RP-001','RP-001-A002-0001')
    apply(root,prepare(root,repair_event(),'work/repair',SHA,manifest=manifest,defects=registry,reachable=lambda _:True))


def test_old_proven_resolution_survives_a_new_repair_without_accepting_new_attempt(accepted):
    reopen_after_old_resolution(accepted)
    assert validate(accepted,reachable=lambda _:True)['verified']==0
    assert load(accepted,REGISTRY)['defects']['DEF-001']['status']=='RESOLVED'
    assert load(accepted,REGISTRY)['defects']['DEF-002']['status']=='OPEN'
    assert load(accepted,MANIFEST)['steps']['RP-001']['revalidation_required']


@pytest.mark.parametrize('case',['unreviewed','wrong-source','wrong-attempt','no-receipt','missing-artifact'])
def test_historical_resolution_cannot_use_forged_or_missing_proof(accepted,case):
    reopen_after_old_resolution(accepted)
    path=PLAN+'/evidence/RP-001/A001/C1.json'
    if case=='unreviewed':update(accepted,path,lambda r:r.update(reviewed=False))
    elif case=='wrong-source':update(accepted,path,lambda r:r.update(source_ref='b'*40))
    elif case=='wrong-attempt':update(accepted,path,lambda r:r.update(attempt='A002'))
    elif case=='missing-artifact':update(accepted,path,lambda r:r.update(artifacts=['docs/absent.md']))
    elif case=='no-receipt':update(accepted,MANIFEST,lambda m:m['steps']['RP-001']['acceptance_history'][0]['check_evidence'].update({'RP-001.C1':[]}))
    with pytest.raises(LedgerError):validate(accepted,reachable=lambda _:True)
