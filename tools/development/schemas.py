"""Closed, versioned public development-record schemas (JSON Schema 2020-12).

Text is reviewed public prose, not a sink for raw provider output. Shape checks
and secret detection supplement, and never replace, human publication review.
"""

TEXT = {"type": "string", "minLength": 1, "maxLength": 8000}
SHA = {"type": "string", "pattern": "^[0-9a-f]{40}$"}
STEP = {"type": "string", "pattern": "^RP-[0-9]{3}$"}
CHECK = {"type": "string", "pattern": r"^RP-[0-9]{3}\.C[1-9][0-9]*$"}
ATTEMPT = {"type": "string", "pattern": "^A[0-9]{3}$"}
PATH = {"type": "string", "pattern": r"^docs/[A-Za-z0-9_./-]+$"}
STATUSES = ["PLANNED", "IN_PROGRESS", "BLOCKED", "VERIFIED", "SUPERSEDED"]


def array(item):
    return {"type": "array", "items": item, "uniqueItems": True}


def closed(properties, required=None):
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


EVENT = closed({
    "schema_version": {"const": 1}, "event_id": TEXT,
    "sequence": {"type": "integer", "minimum": 1},
    "at": {"type": "string", "format": "date-time"}, "item": STEP,
    "check": CHECK, "attempt": ATTEMPT, "phase": TEXT,
    "event": {"enum": ["INTENT", "STARTED", "OUTCOME", "OBSERVATION",
                         "CORRECTION", "RECONCILED", "BLOCKED"]},
    "action_id": {"type": "string", "pattern": "^[A-Z0-9-]+$"},
    "related_event": {"type": ["string", "null"]}, "source_ref": SHA,
    "scope": TEXT, "procedure": TEXT, "expected": TEXT,
    "observed": {"type": ["string", "null"], "maxLength": 8000},
    "outcome": {"enum": ["PENDING", "STARTED", "PASS", "FAIL", "UNKNOWN", "BLOCKED", "RECORDED"]},
    "evidence": array(PATH), "rollback": TEXT, "next_action": TEXT,
    "uncertainty": TEXT,
    "exit_code": {"type": ["integer", "null"]},
    "run_id": TEXT,
    "action_case_correction": closed({
        "old_value": {"type": "string", "pattern": "^[a-z0-9-]+$"},
        "new_value": {"type": "string", "pattern": "^[A-Z0-9-]+$"},
    }),
    "reference_correction": closed({
        "field": {"const": "related_event"},
        "old_value": {"type": ["string", "null"]},
        "new_value": TEXT,
    }),
    "intent_note_correction": closed({
        "field": {"const": "observed"},
        "old_value": TEXT,
        "new_value": {"const": None},
    }),
    "started_metadata_correction": closed({
        "old_outcome": {"const": "RUNNING"},
        "new_outcome": {"const": "PENDING"},
        "old_run_id": {"const": None},
        "new_run_id": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9 ._:/-]{0,255}$"},
    }),
}, ["schema_version", "event_id", "sequence", "at", "item", "check",
    "attempt", "phase", "event", "action_id", "related_event", "source_ref",
    "scope", "procedure", "expected", "observed", "outcome", "evidence",
    "rollback", "next_action", "uncertainty"])

ACCEPTANCE = closed({
    "attempt": ATTEMPT, "completed_checks": array(CHECK),
    "check_evidence": {"type": "object", "propertyNames": CHECK,
                       "additionalProperties": array(PATH)},
    "evidence": array(PATH), "defect": {"type": "string", "pattern": "^DEF-[0-9]{3}$"},
})

STEP_RECORD = closed({
    "title": TEXT, "status": {"enum": STATUSES}, "definition": TEXT,
    "depends_on": array(STEP), "requirements": array({"type": "string", "pattern": "^R[0-9]{2}$"}),
    "completed_checks": array(CHECK), "evidence": array(PATH),
    "amendments": array(PATH), "active_attempt": {"anyOf": [ATTEMPT, {"type": "null"}]},
    "check_evidence": {"type": "object", "propertyNames": CHECK,
                       "additionalProperties": array(PATH)},
    "revalidation_required": array(TEXT),
})
STEP_RECORD["properties"]["acceptance_history"] = array(ACCEPTANCE)

MANIFEST = closed({
    "schema_version": {"const": 1}, "revision": {"const": "R2"},
    "status_authority": PATH, "baseline_commit": SHA,
    "authorization": {"enum": ["PLANNING_ONLY", "PUBLIC_IMPLEMENTATION_AUTHORIZED"]},
    "current_step": STEP, "execution_started": {"type": "boolean"},
    "statuses": {"const": STATUSES},
    "steps": {"type": "object", "minProperties": 1, "propertyNames": STEP,
              "additionalProperties": STEP_RECORD},
})

EVIDENCE = closed({
    "schema_version": {"const": 1}, "item": STEP, "check": CHECK,
    "attempt": ATTEMPT, "source_ref": SHA,
    "result": {"enum": ["PASS", "FAIL", "UNKNOWN"]},
    "reviewed": {"type": "boolean"}, "review_method": TEXT,
    "procedure": TEXT, "expected": TEXT, "observed": TEXT,
    "exit_code": {"type": "integer"}, "platform_scope": TEXT,
    "negative_cases": array(TEXT), "unverified_scope": TEXT,
    "privacy_review": {"const": "PUBLIC_SAFE_REVIEWED"},
    "rollback": TEXT, "intent_event": TEXT, "outcome_event": TEXT,
    "artifacts": array(PATH),
})

CURSOR = closed({
    "schema_version": {"const": 1}, "revision": {"const": "R2"},
    "work_item": TEXT, "check": CHECK, "attempt": ATTEMPT, "phase": TEXT,
    "source_branch": {"type": "string", "pattern": "^[A-Za-z0-9_./-]+$"},
    "source_commit": SHA, "journal": PATH, "last_verified_event": TEXT,
    "last_completed": TEXT, "next_action": TEXT, "verification": TEXT,
    "execution_authorization": {"enum": ["PUBLIC_IMPLEMENTATION_AUTHORIZED", "DOCUMENTATION_AND_PLANNING_ONLY"]},
    "runtime_actions_allowed": {"type": "boolean"},
    "implementation_started": {"type": "boolean"},
    "unsettled_intents": array(TEXT), "expected_user_action": {"type": ["string", "null"]},
    "blocking_decisions": array(TEXT), "known_open_defects": array(TEXT),
    "rollback": TEXT, "next_implementation_step": STEP, "next_implementation_check": CHECK,
    "validation": PATH,
}, ["schema_version", "revision", "work_item", "attempt", "phase", "source_branch",
    "source_commit", "journal", "last_verified_event", "next_action", "verification",
    "execution_authorization", "runtime_actions_allowed", "implementation_started",
    "unsettled_intents", "expected_user_action", "rollback"])
