"""Typed public defect provenance and pure, reviewable repair candidates.

No issue API, workload, publication or acceptance shortcut is implemented here.
Candidates use the existing checkpoint protocol; evidence remains authoritative.
"""
from __future__ import annotations

import copy
import json
import re

from . import schemas as s
from .ledger import PLAN, public_data, public_path, require, shape

REGISTRY = PLAN + "/defects.yaml"
WORK = {"type": "string", "pattern": r"^(RP-\d{3}(\.C\d+)?|IP-\d+|PLAN-R2)$"}
NULL_SHA = {"anyOf": [s.SHA, {"type": "null"}]}
ORIGIN = {"anyOf": [s.closed({"work_item": {"anyOf": [WORK, {"type": "null"}]},
                             "source_ref": NULL_SHA, "evidence": s.array(s.PATH)}), {"type": "null"}]}
HYPOTHESIS = s.closed({"id": s.TEXT, "claim": s.TEXT,
                       "result": {"enum": ["UNTESTED", "FAILED", "SUPPORTED"]},
                       "evidence": s.array(s.PATH)})
REPAIR = s.closed({"item": s.STEP, "attempt": s.ATTEMPT, "intent_event": s.TEXT,
                  "rechecks": {"type": "object", "propertyNames": s.STEP,
                               "additionalProperties": s.closed({"attempt": s.ATTEMPT, "checks": s.array(s.CHECK)})}})
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
            for item, target in repair["rechecks"].items():
                checks = target["checks"]
                require(item in steps and checks, "REPAIR_RECHECK_MISSING")
                step = steps[item]
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
            require(all(steps[item]["status"] == "VERIFIED" for repair in defect["repairs"] for item in repair["rechecks"]),
                    "DEFECT_RESOLUTION_UNPROVEN")


def validate_registry_history(old, new, old_manifest):
    if old["schema_version"] == 1:
        require(new == migrate(old, old_manifest), "DEFECT_MIGRATION_CHANGED_MEANING")
        return
    require(old["defects"].keys() <= new["defects"].keys(), "DEFECT_HISTORY_REMOVED")
    for key, before in old["defects"].items():
        after = new["defects"][key]
        require(before["legacy_record"] == after["legacy_record"], "DEFECT_HISTORY_REWRITTEN")
        for field in ("hypotheses", "repairs"):
            require(after[field][:len(before[field])] == before[field], "DEFECT_HISTORY_REWRITTEN")
        if before["status"] == "OPEN" and after["status"] == "RESOLVED":
            require(len(after["repairs"]) > 0 and after["reproduction"]["passing_source"]
                    and after["resolution_evidence"] and after["regression_test"], "DEFECT_RESOLUTION_UNPROVEN")


def open_repair(manifest, registry, defect_id, responsible, intent_event):
    """Build an isolated attempt and hold transitive previously accepted work.

    A never-started dependent stays PLANNED. Caller must publish this candidate
    with its matching new-attempt INTENT through checkpoint.prepare/publish.
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
    rechecks = {}
    for item in sorted(affected):
        step = steps[item]
        if step["status"] == "PLANNED":
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
    defect["repairs"].append(dict(item=responsible, attempt=attempt, intent_event=intent_event, rechecks=rechecks))
    manifest["current_step"] = responsible
    return manifest, registry
