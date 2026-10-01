"""Typed public defect provenance and pure, reviewable repair candidates.

No issue API, workload, publication or acceptance shortcut is implemented here.
Candidates use the existing checkpoint protocol; evidence remains authoritative.
"""
from __future__ import annotations

import copy
import json
import re

from . import schemas as s
from .ledger import PLAN, load, public_data, public_path, require, shape
from .ledger import validate_journal

REGISTRY = PLAN + "/defects.yaml"
WORK = {"type": "string", "pattern": r"^(RP-\d{3}(\.C\d+)?|IP-\d+|PLAN-R2)$"}
NULL_SHA = {"anyOf": [s.SHA, {"type": "null"}]}
ORIGIN = {"anyOf": [s.closed({"work_item": {"anyOf": [WORK, {"type": "null"}]},
                             "source_ref": NULL_SHA, "evidence": s.array(s.PATH)}), {"type": "null"}]}
HYPOTHESIS = s.closed({"id": s.TEXT, "claim": s.TEXT,
                       "result": {"enum": ["UNTESTED", "FAILED", "SUPPORTED"]},
                       "evidence": s.array(s.PATH)})
UNACCEPTED = s.closed({"attempt": s.ATTEMPT, "suspend_intent": s.TEXT,
                       "suspend_outcome": s.TEXT, "frozen_step": s.STEP_RECORD})
RECONCILIATION = {"type": "object", "minProperties": 1, "propertyNames": s.STEP,
                  "additionalProperties": UNACCEPTED}
REPAIR = s.closed({"item": s.STEP, "attempt": s.ATTEMPT, "intent_event": s.TEXT,
                  "rechecks": {"type": "object", "propertyNames": s.STEP,
                               "additionalProperties": s.closed({"attempt": s.ATTEMPT, "checks": s.array(s.CHECK)})},
                  "reconciled_unaccepted": RECONCILIATION},
                 ["item", "attempt", "intent_event", "rechecks"])
DEFECT = s.closed({
    "title": s.TEXT, "status": {"enum": ["OPEN", "RESOLVED"]}, "detected_in": WORK,
    "suspected_origin": ORIGIN, "proven_origin": ORIGIN,
    "reproduction": s.closed({"procedure": s.TEXT, "failing_source": NULL_SHA,
                               "passing_source": NULL_SHA, "evidence": s.array(s.PATH)}),
    "repair_steps": s.array(s.STEP), "affected_acceptance": s.array(WORK),
    "affected_requirements": s.array({"type": "string", "pattern": "^R[0-9]{2}$"}),
    "hypotheses": s.array(HYPOTHESIS), "repairs": s.array(REPAIR),
    "issue": {"type": ["string", "null"]}, "regression_test": {"type": ["string", "null"]},
    "resolution_evidence": s.array(s.PATH), "notes": s.TEXT,
    "legacy_record": {"type": ["string", "null"]},
})
REGISTRY_SCHEMA = s.closed({"schema_version": {"const": 2}, "defects": {
    "type": "object", "propertyNames": {"type": "string", "pattern": "^DEF-[0-9]{3}$"},
    "additionalProperties": DEFECT}})


def migrate(old, manifest):
    """Explicit one-time v1 mapping, retaining every original value verbatim.

    Missing proof stays missing. A source guess is never promoted to proven.
    Historical resolved records are preserved, not retroactively reaccepted.
    """
    require(old["schema_version"] == 1, "DEFECT_MIGRATION_VERSION")
    result = {"schema_version": 2, "defects": {}}
    for key, previous in old["defects"].items():
        refs = [previous["evidence_source"]] if previous.get("evidence_source") else []
        hypotheses = []

        def origin(value):
            if value is None:
                return None
            if re.fullmatch(r"[0-9a-f]{40}", value):
                return {"work_item": None, "source_ref": value, "evidence": refs}
            hypotheses.append(dict(id="legacy-suspicion", claim=value, result="UNTESTED", evidence=refs))
            return None

        affected = previous["required_acceptance"]
        requirements = sorted({r for a in affected for r in manifest["steps"][a.split(".")[0]]["requirements"]})
        result["defects"][key] = dict(
            title=previous["title"], status=previous["status"], detected_in=previous["detected_in"],
            suspected_origin=origin(previous.get("suspected_origin")),
            proven_origin=origin(previous.get("proven_origin")),
            reproduction=dict(procedure=previous.get("reproduction", previous.get("rule", "See retained source review journal.")),
                              failing_source=previous.get("first_bad_source"), passing_source=None, evidence=refs),
            repair_steps=previous["repair_steps"], affected_acceptance=affected,
            affected_requirements=requirements, hypotheses=hypotheses, repairs=[],
            issue=previous.get("issue"), regression_test=None,
            resolution_evidence=previous.get("resolution_evidence", refs if previous["status"] == "RESOLVED" else []),
            notes="Historical v1 migration; omitted proof remains unknown. Original fields retained in legacy_record.",
            legacy_record=json.dumps(previous, sort_keys=True, separators=(",", ":")))
    return result


def historical_acceptance(root, item, target, step, reachable, events):
    """A past resolution may survive reopening, but only with original PASS proof."""
    require(step['active_attempt'] > target['attempt'], 'DEFECT_RESOLUTION_UNPROVEN')
    histories = [h for h in step.get('acceptance_history', []) if h['attempt'] == target['attempt']]
    require(len(histories) == 1, 'DEFECT_RESOLUTION_UNPROVEN')
    history = histories[0]
    require(set(target['checks']) <= set(history['completed_checks']), 'DEFECT_RESOLUTION_UNPROVEN')
    for check in target['checks']:
        references = history['check_evidence'].get(check, [])
        require(references and set(references) <= set(history['evidence']), 'DEFECT_RESOLUTION_UNPROVEN')
        for reference in references:
            require(reference.startswith(f"{PLAN}/evidence/{item}/{target['attempt']}/")
                    and reference.endswith('.json'), 'DEFECT_RESOLUTION_UNPROVEN')
            receipt = load(root, reference)
            shape(receipt, s.EVIDENCE)
            require((receipt['item'],receipt['check'],receipt['attempt']) == (item,check,target['attempt'])
                    and receipt['result'] == 'PASS' and receipt['reviewed'] and receipt['exit_code'] == 0
                    and reachable(receipt['source_ref']), 'DEFECT_RESOLUTION_UNPROVEN')
            intent, outcome = events.get(receipt['intent_event'], {}), events.get(receipt['outcome_event'], {})
            require(intent.get('event') == 'INTENT' and outcome.get('event') in {'OUTCOME','RECONCILED'}
                    and outcome.get('related_event') == intent.get('event_id') and outcome.get('outcome') == 'PASS'
                    and outcome.get('source_ref') == receipt['source_ref']
                    and all(row.get('item') == item and row.get('attempt') == target['attempt']
                            for row in (intent,outcome)), 'DEFECT_RESOLUTION_UNPROVEN')
            public_data(receipt)
            for artifact in receipt['artifacts']:
                public_path(root, artifact)


def _unaccepted(item, record):
    step = record["frozen_step"]
    require(step["status"] in {"IN_PROGRESS", "BLOCKED"}
            and step["active_attempt"] == record["attempt"]
            and not step["completed_checks"] and not step["check_evidence"]
            and not step.get("acceptance_history"), "REPAIR_RECONCILIATION_NOT_UNACCEPTED")
    checks = step["revalidation_required"]
    require(checks and len(checks) == len(set(checks))
            and all(re.fullmatch(re.escape(item) + r"\.C[1-9][0-9]*", c) for c in checks),
            "REPAIR_RECONCILIATION_HOLD_MISSING")
    return step


def _suspension(repair, events, reachable):
    opening = events[repair["intent_event"]]
    for item, record in repair.get("reconciled_unaccepted", {}).items():
        frozen = _unaccepted(item, record)
        require(item != repair["item"] and repair["rechecks"].get(item) == dict(
            attempt=record["attempt"], checks=frozen["revalidation_required"]),
            "REPAIR_RECONCILIATION_IMPACT_INVALID")
        intent = events.get(record["suspend_intent"], {})
        outcome = events.get(record["suspend_outcome"], {})
        require(intent.get("event") == "INTENT" and intent.get("item") == item
                and intent.get("attempt") == record["attempt"]
                and intent.get("action_id") == "SUSPEND-UNACCEPTED-FOR-PREREQUISITE-REPAIR"
                and outcome.get("event") in {"OUTCOME", "RECONCILED"}
                and outcome.get("outcome") == "RECORDED"
                and outcome.get("related_event") == intent.get("event_id")
                and all(outcome.get(k) == intent.get(k) for k in
                        ("item", "attempt", "check", "source_ref", "action_id")),
                "REPAIR_SUSPENSION_UNPROVEN")
        from datetime import datetime
        timestamp = lambda row: datetime.fromisoformat(row["at"].replace("Z", "+00:00"))
        require(timestamp(intent) <= timestamp(outcome) <= timestamp(opening)
                and intent["sequence"] < outcome["sequence"], "REPAIR_SUSPENSION_ORDER_INVALID")
        # Check the journal at the freeze, not its later resumed state. UNKNOWN
        # and BLOCKED observations do not settle an earlier action.
        prefix = sorted((e for e in events.values() if e["item"] == item
                         and e["attempt"] == record["attempt"]
                         and e["sequence"] <= outcome["sequence"]), key=lambda e: e["sequence"])
        _, pending = validate_journal(prefix, item, record["attempt"], reachable)
        require(not pending, "REPAIR_SUSPENSION_UNSETTLED")


def validate_registry(root, registry, manifest, reachable, events):
    shape(registry, REGISTRY_SCHEMA)
    public_data(registry)
    steps = manifest["steps"]
    requirements = {r for step in steps.values() for r in step["requirements"]}
    for defect in registry["defects"].values():
        require(set(defect["repair_steps"]) <= steps.keys(), "DEFECT_STEP_MISSING")
        require(set(defect["affected_requirements"]) <= requirements, "DEFECT_REQUIREMENT_MISSING")
        for item in [defect["detected_in"], *defect["affected_acceptance"]]:
            if item.startswith("RP-"):
                require(item.split(".")[0] in steps, "DEFECT_STEP_MISSING")
                if "." in item:
                    definition = public_path(root, PLAN + "/" + steps[item.split(".")[0]]["definition"]).read_text(encoding="utf-8")
                    require(f"**{item}**" in definition, "DEFECT_CHECK_MISSING")
        for origin in (defect["suspected_origin"], defect["proven_origin"]):
            if origin:
                require(origin["work_item"] or origin["source_ref"], "DEFECT_ORIGIN_EMPTY")
                if origin["work_item"] and origin["work_item"].startswith("RP-"):
                    require(origin["work_item"].split(".")[0] in steps, "DEFECT_STEP_MISSING")
                if origin is defect["proven_origin"]:
                    require(origin["evidence"], "DEFECT_ORIGIN_UNPROVEN")
        def references(value):
            if isinstance(value, dict):
                for field, child in value.items():
                    if field in {"source_ref", "failing_source", "passing_source"} and child:
                        require(reachable(child), "PUBLIC_COMMIT_MISSING")
                    elif field in {"evidence", "resolution_evidence"}:
                        for path in child:
                            public_path(root, path)
                    else:
                        references(child)
            elif isinstance(value, list):
                for child in value:
                    references(child)
        references(defect)
        require(len({h["id"] for h in defect["hypotheses"]}) == len(defect["hypotheses"]), "HYPOTHESIS_ID_REUSED")
        require(len({(r["item"], r["attempt"]) for r in defect["repairs"]}) == len(defect["repairs"]), "REPAIR_ATTEMPT_REUSED")
        for repair in defect["repairs"]:
            intent = events.get(repair["intent_event"], {})
            require(repair["item"] in defect["repair_steps"] and intent.get("event") == "INTENT"
                    and intent.get("item") == repair["item"] and intent.get("attempt") == repair["attempt"],
                    "REPAIR_INTENT_MISSING")
            _suspension(repair, events, reachable)
            for item, target in repair["rechecks"].items():
                checks = target["checks"]
                require(item in steps and checks, "REPAIR_RECHECK_MISSING")
                step = steps[item]
                definition = public_path(root, PLAN + "/" + step["definition"]).read_text(encoding="utf-8")
                defined = set(re.findall(r"^- \[[ x]\] \*\*(RP-\d{3}\.C\d+)\*\*", definition, re.M))
                require(set(checks) == defined, "REPAIR_RECHECK_INCOMPLETE")
                require(step["active_attempt"] is not None and step["active_attempt"] >= target["attempt"],
                        "REPAIR_ACCEPTANCE_STALE")
                if step["status"] == "VERIFIED":
                    require(set(checks) <= set(step["completed_checks"]), "REPAIR_RECHECK_MISSING")
                else:
                    require(set(checks) <= set(step["revalidation_required"]), "REPAIR_HOLD_REMOVED")
        if defect["status"] == "RESOLVED" and defect["legacy_record"] is None:
            require(defect["repairs"] and defect["resolution_evidence"]
                    and defect["reproduction"]["passing_source"] and defect["regression_test"],
                    "DEFECT_RESOLUTION_UNPROVEN")
            for repair in defect['repairs']:
                for item, target in repair['rechecks'].items():
                    if steps[item]['status'] != 'VERIFIED':
                        historical_acceptance(root, item, target, steps[item], reachable, events)


def validate_registry_history(old, new, old_manifest, new_manifest=None):
    new_manifest = old_manifest if new_manifest is None else new_manifest
    if old["schema_version"] == 1:
        migrated = migrate(old, old_manifest)
        require(all(new["defects"].get(key) == record for key, record in migrated["defects"].items()),
                "DEFECT_MIGRATION_CHANGED_MEANING")
        old = migrated
    require(old["defects"].keys() <= new["defects"].keys(), "DEFECT_HISTORY_REMOVED")
    for key in new["defects"].keys() - old["defects"].keys():
        require(new["defects"][key]["legacy_record"] is None, "DEFECT_LEGACY_EXEMPTION_FORGED")
    for key, before in old["defects"].items():
        after = new["defects"][key]
        require(before["legacy_record"] == after["legacy_record"], "DEFECT_HISTORY_REWRITTEN")
        for field in ("hypotheses", "repairs"):
            require(after[field][:len(before[field])] == before[field], "DEFECT_HISTORY_REWRITTEN")
        if before["status"] == "OPEN" and after["status"] == "RESOLVED":
            require(len(after["repairs"]) > 0 and after["reproduction"]["passing_source"]
                    and after["resolution_evidence"] and after["regression_test"], "DEFECT_RESOLUTION_UNPROVEN")
    additions = []
    for key, after in new["defects"].items():
        previous_repairs = old["defects"].get(key, {}).get("repairs", [])
        for repair in after["repairs"][len(previous_repairs):]:
            additions.append((repair["item"], repair["attempt"], repair["intent_event"], key, repair))
    opened = {}
    for _, _, _, key, repair in sorted(additions):
            after = new["defects"][key]
            previous_repairs = old["defects"].get(key, {}).get("repairs", [])
            item = repair["item"]
            require(item in old_manifest["steps"], "DEFECT_STEP_MISSING")
            previous_step = old_manifest["steps"][item]
            opening = opened.get((item, repair["attempt"]))
            if opening is not None:
                # The first repair already proved the accepted-build snapshot
                # and transitive impact. A later defect belongs to that active
                # attempt; it must not fabricate a second historical acceptance.
                require(repair["intent_event"] > opening, "REPAIR_ATTEMPT_INVALID")
                previous_step = {**previous_step, "status":"IN_PROGRESS",
                                 "active_attempt":repair["attempt"]}
            if previous_step["status"] == "VERIFIED":
                candidate_registry = copy.deepcopy(old)
                candidate_registry["defects"][key] = copy.deepcopy(after)
                candidate_registry["defects"][key]["repairs"] = copy.deepcopy(previous_repairs)
                reconciled = repair.get("reconciled_unaccepted")
                baseline = copy.deepcopy(old_manifest)
                for target, record in (reconciled or {}).items():
                    require(target in baseline["steps"], "DEFECT_STEP_MISSING")
                    previous = baseline["steps"][target]
                    frozen = _unaccepted(target, record)
                    require(previous["status"] in {"PLANNED", "IN_PROGRESS", "BLOCKED"}
                            and not previous["completed_checks"] and not previous["check_evidence"]
                            and not previous.get("acceptance_history")
                            and previous["active_attempt"] in {None, record["attempt"]}
                            and all(previous[k] == frozen[k] for k in
                                    ("title", "definition", "depends_on", "requirements"))
                            and set(previous["evidence"]) <= set(frozen["evidence"])
                            and set(previous["amendments"]) <= set(frozen["amendments"]),
                            "REPAIR_RECONCILIATION_BASE_INVALID")
                    # A history base may predate this dependent's first start.
                    # Its explicit never-accepted freeze, separately proved by
                    # the journal, is not an accepted-build snapshot.
                    baseline["steps"][target] = copy.deepcopy(frozen)
                expected_manifest, expected_registry = open_repair(baseline, candidate_registry, key, item,
                                                                   repair["intent_event"],
                                                                   reconciled_unaccepted=reconciled)
                require(repair == expected_registry["defects"][key]["repairs"][-1], "REPAIR_IMPACT_INCOMPLETE")
                for target in repair["rechecks"]:
                    if target in (reconciled or {}):
                        current = new_manifest["steps"][target]
                        require(current["active_attempt"] >= reconciled[target]["attempt"],
                                "REPAIR_ACCEPTANCE_STALE")
                        if current["active_attempt"] == reconciled[target]["attempt"]:
                            require(not current.get("acceptance_history"), "REPAIR_UNACCEPTED_SNAPSHOT_FORGED")
                        continue
                    snapshot = expected_manifest["steps"][target]["acceptance_history"][-1]
                    require(snapshot in new_manifest["steps"][target].get("acceptance_history", []),
                            "ACCEPTANCE_SNAPSHOT_MISSING")
                opened[(item, repair["attempt"])] = repair["intent_event"]
            else:
                # A bug found before acceptance is repaired in the active attempt;
                # no previously accepted build exists to reopen or fabricate.
                expected_attempt = "A001" if previous_step["status"] == "PLANNED" else previous_step["active_attempt"]
                require(previous_step["status"] in {"PLANNED", "IN_PROGRESS", "BLOCKED"}
                        and repair["attempt"] == expected_attempt
                        and set(repair["rechecks"]) == {item}, "REPAIR_ATTEMPT_INVALID")


def open_repair(manifest, registry, defect_id, responsible, intent_event, *, reconciled_unaccepted=None):
    """Build an isolated attempt and hold transitive previously accepted work.

    A never-started dependent stays PLANNED. An explicitly suspended unaccepted
    dependent retains its attempt/WIP/full holds; default concurrent takeover
    still fails. Caller must publish through checkpoint.prepare/publish, which
    verifies the suspension journal and the complete impact before any action.
    """
    manifest, registry = copy.deepcopy(manifest), copy.deepcopy(registry)
    defect = registry["defects"][defect_id]
    require(responsible in defect["repair_steps"], "REPAIR_OWNER_INVALID")
    steps = manifest["steps"]
    require(steps[responsible]["status"] == "VERIFIED", "REPAIR_REQUIRES_ACCEPTED_STEP")
    affected = {responsible} | {a.split(".")[0] for a in defect["affected_acceptance"]}
    while True:
        expanded = affected | {k for k, v in steps.items() if set(v["depends_on"]) & affected}
        if expanded == affected:
            break
        affected = expanded
    reconciled = {} if reconciled_unaccepted is None else reconciled_unaccepted
    if reconciled_unaccepted is not None:
        shape(reconciled, RECONCILIATION)
        active = {k for k in affected if steps[k]["status"] not in {"PLANNED", "VERIFIED"}}
        require(set(reconciled) == active, "REPAIR_RECONCILIATION_SCOPE_INVALID")
        dependents = {responsible}
        while True:
            expanded = dependents | {k for k, v in steps.items() if set(v["depends_on"]) & dependents}
            if expanded == dependents:
                break
            dependents = expanded
        require(set(reconciled) <= dependents - {responsible}, "REPAIR_RECONCILIATION_SCOPE_INVALID")
    rechecks = {}
    for item in sorted(affected):
        step = steps[item]
        if step["status"] == "PLANNED":
            continue
        if item in reconciled:
            frozen = _unaccepted(item, reconciled[item])
            require(step == frozen, "REPAIR_RECONCILIATION_SNAPSHOT_MISMATCH")
            step["status"] = "BLOCKED"
            rechecks[item] = dict(attempt=step["active_attempt"], checks=list(step["revalidation_required"]))
            continue
        require(step["status"] == "VERIFIED", "REPAIR_CONCURRENT_WORK_REQUIRES_RECONCILIATION")
        history = dict(attempt=step["active_attempt"], completed_checks=list(step["completed_checks"]),
                       check_evidence=copy.deepcopy(step["check_evidence"]), evidence=list(step["evidence"]), defect=defect_id)
        step.setdefault("acceptance_history", []).append(history)
        checks = list(step["completed_checks"])
        number = int(step["active_attempt"][1:]) + 1
        require(number <= 999, "REPAIR_ATTEMPT_EXHAUSTED")
        step.update(status="IN_PROGRESS" if item == responsible else "BLOCKED", active_attempt=f"A{number:03d}",
                    completed_checks=[], check_evidence={}, revalidation_required=checks)
        rechecks[item] = dict(attempt=step["active_attempt"], checks=checks)
    attempt = steps[responsible]["active_attempt"]
    require(intent_event == f"{responsible}-{attempt}-0001", "REPAIR_INTENT_ID_INVALID")
    defect["status"] = "OPEN"
    repair = dict(item=responsible, attempt=attempt, intent_event=intent_event, rechecks=rechecks)
    if reconciled:
        repair["reconciled_unaccepted"] = copy.deepcopy(reconciled)
    defect["repairs"].append(repair)
    manifest["current_step"] = responsible
    return manifest, registry
