"""Unreleased RP-010 wire schemas and executable specification, not runtime IO.

The model CAS is an explicit hypothesis. Production storage, authorization,
durable process supervision and publication are separate implementation gates.
"""
from __future__ import annotations

import copy
import hashlib
import json

from jsonschema import Draft202012Validator, FormatChecker

from tb4.exchange_layout import MAX_GENERATION, LayoutError, encoded, slots, Capacity
from tb4.privacy import closed


ID = {"type": "string", "pattern": "^[a-f0-9]{64}$"}
UUID = {"type": "string", "format": "uuid"}
GENERATION = {"type": "integer", "minimum": 1, "maximum": MAX_GENERATION}
TIME = {"type": "integer", "minimum": 0, "maximum": 10**12}
NULL_TIME = {"anyOf": [TIME, {"type": "null"}]}
BINDING_PROPERTIES = {"domain_id": UUID, "target_id": UUID, "operation_id": ID,
                      "generation": GENERATION, "protocol_major": {"const": 2, "type": "integer"},
                      "protocol_minor": {"const": 0, "type": "integer"}, "payload_sha256": ID}
BINDING = closed(BINDING_PROPERTIES)
PAYLOAD = {"oneOf": [
    closed({"kind": {"const": "INLINE"}, "interpreter": {"enum": ["python", "python3", "pwsh", "powershell", "bash", "sh"]},
            "size_bytes": {"type": "integer", "minimum": 1, "maximum": 256},
            "text": {"type": "string", "minLength": 1, "maxLength": 256}}),
    closed({"kind": {"const": "ARTIFACT"}, "interpreter": {"enum": ["python", "python3", "pwsh", "powershell", "bash", "sh"]},
            "size_bytes": {"type": "integer", "minimum": 1, "maximum": 8388608},
            "slot": {"type": "string", "pattern": r"^artifact\.[0-9]{3}\.input$"},
            "artifact_generation": GENERATION}),
]}
REQUEST = closed({**BINDING_PROPERTIES, "kind": {"const": "SUBMIT"},
                  "given_at": TIME, "claim_deadline": TIME,
                  "run_limit_s": {"type": "integer", "minimum": 1, "maximum": 86400},
                  "payload": PAYLOAD})
RESULT = closed({"binding": BINDING, "outcome": {"enum": ["DONE", "PARTIAL", "FAILED", "CANCELLED"]},
                 "execution": {"enum": ["EXITED", "INTERRUPTED", "NOT_EXECUTED"]},
                 "exit_code": {"type": ["integer", "null"], "minimum": -2147483648, "maximum": 2147483647},
                 "interruption_proven": {"type": "boolean"},
                 "effects": {"enum": ["NONE", "KNOWN", "UNKNOWN"]},
                 "reason": {"enum": ["EXIT_ZERO", "EXIT_NONZERO", "INTERRUPTED", "CLAIM_EXPIRED", "WITHDRAWN"]},
                 "stdout_tail": {"type": "string", "maxLength": 128},
                 "stderr_tail": {"type": "string", "maxLength": 128},
                 "artifact_output": {"anyOf": [{"type":"null"}, closed({
                     "slot":{"type":"string", "pattern":r"^artifact\.[0-9]{3}\.output$"},
                     "generation":GENERATION, "sha256":ID,
                     "size_bytes":{"type":"integer", "minimum":0, "maximum":8388608}})]},
                 "result_sha256": ID})
CANCEL = closed({"binding": BINDING, "request_id": ID, "requested_at": TIME,
                 "state": {"enum": ["REQUESTED", "ACKNOWLEDGED", "SIGNALLED", "ALREADY_FINISHED", "UNKNOWN"]}})
ACK = closed({"binding": BINDING, "result_sha256": ID, "consumed_at": TIME})
STATUS = closed({"binding": BINDING,
                 "receipt": {"enum": ["ADMITTED", "REJECTED"]},
                 "execution": {"enum": ["NOT_STARTED", "CLAIMED", "RUNNING", "EXITED", "INTERRUPTED", "NOT_EXECUTED", "UNKNOWN"]},
                 "publication": {"enum": ["NONE", "PENDING", "CONFIRMED"]},
                 "consumption": {"enum": ["NOT_READY", "PENDING", "ACKNOWLEDGED"]},
                 "stage": {"enum": ["WAITING_HOST", "WAITING_FETCHER", "QUEUED", "CLAIMED", "EXECUTING", "RETURNING", "WAITING_RESULT", "AWAITING_CONSUMPTION", "RECYCLING", "READY"]},
                 "responsible": {"enum": ["WATCHDOG", "FETCHER", "COACH"]},
                 "stage_at": TIME, "last_progress_at": TIME,
                 "wait_reason": {"enum": ["NONE", "HOST", "FETCHER", "EXECUTION", "EXECUTION_UNKNOWN", "PUBLICATION", "RESULT_ACK", "RECYCLE"]},
                 "next_check_at": NULL_TIME, "deadline_at": NULL_TIME,
                 "terminal": {"type": "boolean"}, "result_sha256": {"anyOf": [ID, {"type": "null"}]}})
REJECTION_CODES = ["MALFORMED", "SCHEMA", "WRONG_DOMAIN", "UNKNOWN_TARGET", "IDENTITY",
                   "PAYLOAD_INTEGRITY", "ARTIFACT_UNVERIFIED", "TIME_RANGE", "EXPIRED", "FUTURE_REQUEST",
                   "TOO_LARGE", "ID_CONFLICT", "BUSY", "STALE_GENERATION", "GENERATION_GAP", "CAPACITY"]
RECEIPT = closed({"kind": {"const": "INGRESS_RECEIPT"}, "disposition": {"enum": ["ADMITTED", "DUPLICATE", "REJECTED"]},
                  "reason": {"enum": ["ACCEPTED", "EXISTING", *REJECTION_CODES]},
                  "operation_id": {"anyOf": [ID, {"type": "null"}]},
                  "request_sha256": ID, "ingress_slot": {"type": "integer", "minimum": 0, "maximum": 15},
                  "ingress_generation": GENERATION,
                  "ingress_revision": {"type": "string", "minLength": 1, "maxLength": 128}})
SCHEMAS = {"request": REQUEST, "binding": BINDING, "result": RESULT, "cancel": CANCEL,
           "ack": ACK, "status_projection": STATUS, "receipt": RECEIPT}


class ContractError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ContractError(code)


def validate_shape(kind, value):
    require(kind in SCHEMAS, "SCHEMA")
    def no_float(node):
        if isinstance(node, dict):
            return all(no_float(item) for item in node.values())
        if isinstance(node, list):
            return all(no_float(item) for item in node)
        return type(node) is not float
    require(no_float(value), "SCHEMA")
    validator = Draft202012Validator(SCHEMAS[kind], format_checker=FormatChecker())
    require(not next(validator.iter_errors(value), None), "SCHEMA")
    return value


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def clock_value(now):
    require(type(now) is int and 0 <= now <= 10**12, "TIME_RANGE")


def operation_id(domain_id, target_id, generation):
    # Target generations never rewind, so bounded history can reject an old ID
    # after retention without a forever-growing table of arbitrary client IDs.
    return digest(["TB4-R2-OP", domain_id, target_id, generation])


def binding(request):
    return {key: request[key] for key in BINDING_PROPERTIES}


def decode_request(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "MALFORMED")
            result[key] = value
        return result
    require(type(raw) is bytes and len(raw) <= 1024, "TOO_LARGE")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ContractError("MALFORMED")))
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError("MALFORMED") from None


def validate_request(request, *, domain_id, targets, now, artifacts=None):
    clock_value(now)
    validate_shape("request", request)
    require(request["domain_id"] == domain_id, "WRONG_DOMAIN")
    require(request["target_id"] in targets, "UNKNOWN_TARGET")
    require(request["operation_id"] == operation_id(domain_id, request["target_id"], request["generation"]), "IDENTITY")
    require(request["given_at"] < request["claim_deadline"], "TIME_RANGE")
    require(request["given_at"] <= now, "FUTURE_REQUEST")
    payload = request["payload"]
    if payload["kind"] == "INLINE":
        try:
            raw = payload["text"].encode("utf-8")
        except UnicodeError:
            raise ContractError("PAYLOAD_INTEGRITY") from None
        require(len(raw) == payload["size_bytes"] <= 256
                and hashlib.sha256(raw).hexdigest() == request["payload_sha256"], "PAYLOAD_INTEGRITY")
    else:
        descriptor = (artifacts or {}).get(payload["slot"])
        require(descriptor == {"generation":payload["artifact_generation"],
                "size_bytes":payload["size_bytes"], "sha256":request["payload_sha256"],
                "target_id":request["target_id"], "complete":True}, "ARTIFACT_UNVERIFIED")
    pack_record("ingress.000", request)
    return request


def pack_record(slot, request):
    """Common ingress/work request encoding; other views use their explicit codec."""
    body = {k:v for k,v in request.items() if k not in {"operation_id", "generation"}}
    record = {"operation_id":request["operation_id"], "generation":request["generation"],
              "retention":"BUSY", "body":body}
    check_budget(slot, record)
    return record


def check_budget(slot, record):
    budgets = slots(Capacity(64,16,128,32))
    try:
        require(slot in budgets and len(encoded({slot:record})) <= budgets[slot], "TOO_LARGE")
    except LayoutError:
        raise ContractError("SCHEMA") from None


def compact_record(kind, value, expected_binding, target_index):
    """Compact leaf derives binding from validated work in the SAME Doc revision.

    It is unsafe to decode one leaf against a separately fetched/new work record.
    Projection schemas remain the semantic interface, not these private leaf bodies.
    """
    require(kind in {"result", "cancel", "ack", "status_projection"}, "SCHEMA")
    validate_shape(kind, value)
    require(value["binding"] == expected_binding, "BINDING")
    require(type(target_index) is int and 0 <= target_index < 64, "TARGET_SLOT")
    if kind == "result":
        validate_result(value, expected_binding)
    leaf = "status" if kind == "status_projection" else kind
    body = {k:copy.deepcopy(v) for k,v in value.items() if k != "binding"}
    if kind == "status_projection":
        # Axes/digest are reconstructed from work/result/ACK in the same snapshot.
        body = {k:body[k] for k in ("stage", "responsible", "stage_at", "last_progress_at",
                                    "wait_reason", "next_check_at", "deadline_at")}
    record = {"operation_id":expected_binding["operation_id"], "generation":expected_binding["generation"],
              "retention":"BUSY", "body":body}
    check_budget(f"target.{target_index:03d}.{leaf}", record)
    return record


def expand_leaf(kind, record, expected_binding):
    require(kind in {"result", "cancel", "ack"}, "SCHEMA")
    require(type(record) is dict and set(record) == {"operation_id", "generation", "retention", "body"}
            and record["operation_id"] == expected_binding["operation_id"]
            and type(record["generation"]) is int and record["generation"] == expected_binding["generation"]
            and record["retention"] in {"BUSY", "UNREAD", "CONSUMED"}
            and type(record["body"]) is dict and "binding" not in record["body"], "BINDING")
    value = {**copy.deepcopy(record["body"]), "binding":copy.deepcopy(expected_binding)}
    validate_shape(kind, value)
    if kind == "result":
        validate_result(value, expected_binding)
    return value


def make_result(request, *, outcome="DONE", execution="EXITED", exit_code=0,
                interruption_proven=False, effects="NONE", reason="EXIT_ZERO",
                stdout_tail="", stderr_tail="", artifact_output=None):
    result = dict(binding=binding(request), outcome=outcome, execution=execution,
                  exit_code=exit_code, interruption_proven=interruption_proven,
                  effects=effects, reason=reason, stdout_tail=stdout_tail,
                  stderr_tail=stderr_tail, artifact_output=artifact_output)
    result["result_sha256"] = digest(result)
    validate_result(result, binding(request))
    return result


def validate_result(result, expected_binding):
    validate_shape("result", result)
    require(result["binding"] == expected_binding, "BINDING")
    require(result["result_sha256"] == digest({k:v for k,v in result.items() if k != "result_sha256"}), "RESULT_INTEGRITY")
    if result["execution"] == "EXITED":
        require(type(result["exit_code"]) is int and not result["interruption_proven"], "RESULT_SEMANTICS")
        success = result["exit_code"] == 0
        expected = "DONE" if success else ("PARTIAL" if result["effects"] == "KNOWN" else "FAILED")
        require(result["outcome"] == expected
                and result["reason"] == ("EXIT_ZERO" if success else "EXIT_NONZERO"), "RESULT_SEMANTICS")
    elif result["execution"] == "NOT_EXECUTED":
        require((result["outcome"], result["reason"]) in {("FAILED", "CLAIM_EXPIRED"), ("CANCELLED", "WITHDRAWN")}
                and result["exit_code"] is None and result["effects"] == "NONE"
                and not result["interruption_proven"], "RESULT_SEMANTICS")
    else:
        require(result["interruption_proven"] and result["outcome"] in {"CANCELLED", "PARTIAL"}
                and result["reason"] == "INTERRUPTED", "RESULT_SEMANTICS")
    return result


class AdmissionModel:
    """Synthetic durable-state image; production commit must be one authority CAS."""
    def __init__(self, domain_id, targets, saved=None):
        self.domain_id, self.targets = domain_id, set(targets)
        self.state = copy.deepcopy(saved) if saved is not None else {
            target:{"generation":0, "current":None, "history":{}} for target in targets}

    def submit(self, raw, *, now, ingress_slot=0, ingress_generation=1, ingress_revision="synthetic-revision", artifacts=None, has_capacity=True):
        # Caller provenance is trusted transport metadata; reject it before any mutation.
        clock_value(now)
        require(type(raw) is bytes, "MALFORMED")
        request = None
        request_hash = hashlib.sha256(raw).hexdigest()
        receipt = dict(kind="INGRESS_RECEIPT", disposition="REJECTED", reason="MALFORMED", operation_id=None,
                       request_sha256=request_hash, ingress_slot=ingress_slot,
                       ingress_generation=ingress_generation, ingress_revision=ingress_revision)
        validate_shape("receipt", receipt)
        disposition, reason, op = "REJECTED", "MALFORMED", None
        try:
            request = decode_request(raw)
            validate_request(request, domain_id=self.domain_id, targets=self.targets, now=now, artifacts=artifacts)
            op = request["operation_id"]
            row = self.state[request["target_id"]]
            fingerprint = digest(request)
            existing = row["current"] if row["current"] and row["current"]["operation_id"] == op else row["history"].get(op)
            if existing:
                require(existing["fingerprint"] == fingerprint, "ID_CONFLICT")
                disposition, reason = "DUPLICATE", "EXISTING"
            else:
                require(row["current"] is None, "BUSY")
                require(request["generation"] > row["generation"], "STALE_GENERATION")
                require(request["generation"] == row["generation"] + 1, "GENERATION_GAP")
                require(now < request["claim_deadline"], "EXPIRED")
                require(has_capacity, "CAPACITY")
                row["generation"] = request["generation"]
                row["current"] = {"operation_id":op, "fingerprint":fingerprint, "request":copy.deepcopy(request)}
                disposition, reason = "ADMITTED", "ACCEPTED"
        except ContractError as error:
            reason = str(error)
        receipt.update(disposition=disposition, reason=reason, operation_id=op)
        validate_shape("receipt", receipt)
        return receipt

    def recycle(self, target, lifecycle, *, retain=8):
        """One conceptual authority transaction; retain compact duplicate receipts."""
        require(type(retain) is int and 1 <= retain <= 128, "CAPACITY")
        row = self.state[target]
        require(row["current"] is not None and lifecycle["stage"] == "READY"
                and lifecycle["consumption"] == "ACKNOWLEDGED"
                and lifecycle["publication"] == "CONFIRMED"
                and lifecycle["binding"] == binding(row["current"]["request"]), "UNCONSUMED")
        current = row["current"]
        row["history"][current["operation_id"]] = {
            "operation_id":current["operation_id"], "fingerprint":current["fingerprint"],
            "result_sha256":lifecycle["result_sha256"]}
        while len(row["history"]) > retain:
            del row["history"][next(iter(row["history"]))]
        row["current"] = None


TRANSITIONS = {
    "wait_host": ("WATCHDOG", {"QUEUED", "WAITING_HOST", "WAITING_FETCHER"}),
    "wait_fetcher": ("WATCHDOG", {"QUEUED", "WAITING_HOST", "WAITING_FETCHER"}),
    "claim": ("FETCHER", {"QUEUED", "WAITING_HOST", "WAITING_FETCHER"}),
    "start": ("FETCHER", {"CLAIMED"}),
    "expire": ("WATCHDOG", {"QUEUED", "WAITING_HOST", "WAITING_FETCHER"}),
    "withdraw": ("WATCHDOG", {"QUEUED", "WAITING_HOST", "WAITING_FETCHER"}),
    "unknown": ("WATCHDOG", {"CLAIMED", "EXECUTING"}),
    "result": ("FETCHER", {"CLAIMED", "EXECUTING", "WAITING_RESULT"}),
    "publish": ("FETCHER", {"RETURNING"}),
    "publish_expiry": ("WATCHDOG", {"RETURNING"}),
    "ack": ("COACH", {"AWAITING_CONSUMPTION"}),
    "recycle": ("WATCHDOG", {"RECYCLING"}),
}


class LifecycleModel:
    def __init__(self, request):
        self.request = copy.deepcopy(request)
        self.state = dict(revision=0, binding=binding(request), receipt="ADMITTED", execution="NOT_STARTED",
            publication="NONE", consumption="NOT_READY", stage="QUEUED", responsible="WATCHDOG",
            stage_at=request["given_at"], last_progress_at=request["given_at"], wait_reason="FETCHER",
            next_check_at=request["given_at"], deadline_at=request["claim_deadline"], terminal=False,
            result_sha256=None, result=None, cancellation=None, history=None)

    def read(self):
        return copy.deepcopy(self.state)

    def status(self):
        value = {key: self.state[key] for key in STATUS["properties"]}
        validate_shape("status_projection", value)
        return copy.deepcopy(value)

    def cancel(self, observed, request, *, actor="COACH"):
        validate_shape("cancel", request)
        require(actor in {"COACH", "FETCHER"}, "CANCEL_ACTOR")
        if observed != self.state or request["binding"] != self.state["binding"]:
            return False
        previous = self.state["cancellation"]
        require(self.state["stage"] != "READY", "CANCEL_FINISHED")
        if previous == request:
            return True
        if previous:
            require(all(previous[k] == request[k] for k in ("binding", "request_id", "requested_at")), "CANCEL_IDENTITY")
        if actor == "COACH":
            require(request["state"] == "REQUESTED", "CANCEL_ACTOR")
            require(previous is None, "CANCEL_TRANSITION")
        else:
            require(actor == "FETCHER" and previous is not None, "CANCEL_ACTOR")
            edges = {"REQUESTED":{"ACKNOWLEDGED", "ALREADY_FINISHED", "UNKNOWN"},
                     "ACKNOWLEDGED":{"SIGNALLED", "ALREADY_FINISHED", "UNKNOWN"},
                     "SIGNALLED":{"ALREADY_FINISHED", "UNKNOWN"}, "UNKNOWN":{"ACKNOWLEDGED", "ALREADY_FINISHED"}}
            require(request["state"] in edges.get(previous["state"], set()), "CANCEL_TRANSITION")
            if request["state"] == "SIGNALLED":
                require(self.state["execution"] in {"CLAIMED", "RUNNING", "UNKNOWN"}, "CANCEL_TRANSITION")
            if request["state"] == "ALREADY_FINISHED":
                require(self.state["execution"] in {"EXITED", "INTERRUPTED", "NOT_EXECUTED"}, "CANCEL_TRANSITION")
        self.state["cancellation"] = copy.deepcopy(request)
        self.state["revision"] += 1
        return True

    def apply(self, observed, event, actor, now, *, result=None, ack=None, readback_digest=None):
        clock_value(now)
        if observed != self.state:
            return False
        require(event in TRANSITIONS, "TRANSITION")
        writer, stages = TRANSITIONS[event]
        require(actor == writer and self.state["stage"] in stages, "TRANSITION")
        require(now >= self.state["last_progress_at"], "TIME_RANGE")
        state = copy.deepcopy(self.state)
        if event in {"wait_host", "wait_fetcher"}:
            state.update(stage="WAITING_HOST" if event == "wait_host" else "WAITING_FETCHER",
                         wait_reason="HOST" if event == "wait_host" else "FETCHER")
        elif event == "claim":
            if now >= self.request["claim_deadline"] or state["cancellation"] is not None:
                return False
            state.update(execution="CLAIMED", stage="CLAIMED", responsible="FETCHER", wait_reason="EXECUTION",
                         deadline_at=now + self.request["run_limit_s"])
        elif event == "start":
            if now >= state["deadline_at"]:
                return False
            state.update(execution="RUNNING", stage="EXECUTING", wait_reason="EXECUTION",
                         deadline_at=now + self.request["run_limit_s"])
        elif event in {"expire", "withdraw"}:
            if event == "expire" and now < self.request["claim_deadline"]:
                return False
            require(event != "withdraw" or state["cancellation"] is not None, "CANCEL_REQUIRED")
            result = make_result(self.request, outcome="CANCELLED" if event == "withdraw" else "FAILED",
                                 execution="NOT_EXECUTED", exit_code=None,
                                 reason="WITHDRAWN" if event == "withdraw" else "CLAIM_EXPIRED")
            state.update(execution="NOT_EXECUTED", result=result, result_sha256=result["result_sha256"],
                         publication="PENDING", stage="RETURNING", wait_reason="PUBLICATION", deadline_at=None)
        elif event == "unknown":
            state.update(execution="UNKNOWN", stage="WAITING_RESULT", wait_reason="EXECUTION_UNKNOWN", deadline_at=None)
        elif event == "result":
            validate_result(result, state["binding"])
            require(result["execution"] != "NOT_EXECUTED", "RESULT_SEMANTICS")
            state.update(execution=result["execution"], result=copy.deepcopy(result), result_sha256=result["result_sha256"],
                         publication="PENDING", stage="RETURNING", responsible="FETCHER", wait_reason="PUBLICATION", deadline_at=None)
        elif event in {"publish", "publish_expiry"}:
            require((event == "publish_expiry") == (state["execution"] == "NOT_EXECUTED"), "TRANSITION")
            require(readback_digest is not None and readback_digest == state["result_sha256"], "PUBLICATION_UNCONFIRMED")
            state.update(publication="CONFIRMED", consumption="PENDING", terminal=True,
                         stage="AWAITING_CONSUMPTION", responsible="COACH", wait_reason="RESULT_ACK", deadline_at=None)
        elif event == "ack":
            validate_shape("ack", ack)
            require(ack["binding"] == state["binding"] and ack["result_sha256"] == state["result_sha256"], "ACK_MISMATCH")
            require(state["stage_at"] <= ack["consumed_at"] <= now, "TIME_RANGE")
            state.update(consumption="ACKNOWLEDGED", stage="RECYCLING", responsible="WATCHDOG", wait_reason="RECYCLE")
        elif event == "recycle":
            require(state["consumption"] == "ACKNOWLEDGED" and state["publication"] == "CONFIRMED", "UNCONSUMED")
            state.update(history={"binding":copy.deepcopy(state["binding"]), "result_sha256":state["result_sha256"], "consumed":True},
                         stage="READY", wait_reason="NONE", result=None, cancellation=None)
        state.update(revision=state["revision"] + 1, stage_at=now, last_progress_at=now,
                     next_check_at=None if state["stage"] == "READY" else min(now + 5, 10**12))
        validate_shape("status_projection", {key:state[key] for key in STATUS["properties"]})
        self.state = state
        return True
