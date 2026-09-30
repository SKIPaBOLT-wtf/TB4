from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tb4.command_contract import (SCHEMAS, TRANSITIONS, AdmissionModel, LifecycleModel,
    ContractError, binding, compact_record, decode_request, digest, expand_leaf,
    make_result, operation_id, pack_record, validate_request, validate_result, validate_shape)
from tb4.exchange_layout import MAX_GENERATION, encoded

DOMAIN = "00000000-0000-4000-8000-000000000001"
TARGET = "00000000-0000-4000-8000-000000000002"
OTHER = "00000000-0000-4000-8000-000000000003"
ROOT = Path(__file__).resolve().parents[2]


def request(target=TARGET, generation=1, text="print('synthetic')"):
    raw = text.encode()
    return dict(domain_id=DOMAIN, target_id=target, generation=generation,
                operation_id=operation_id(DOMAIN, target, generation),
                protocol_major=2, protocol_minor=0, payload_sha256=hashlib.sha256(raw).hexdigest(),
                kind="SUBMIT", given_at=100, claim_deadline=200, run_limit_s=30,
                payload=dict(kind="INLINE", interpreter="python", size_bytes=len(raw), text=text))


def validate(value, **kwargs):
    return validate_request(value, domain_id=DOMAIN, targets={TARGET, OTHER}, now=100, **kwargs)


def cancel_request(req, state="REQUESTED"):
    return dict(binding=binding(req), request_id="c"*64, requested_at=101, state=state)


def ack_request(req, result, when=105):
    return dict(binding=binding(req), result_sha256=result["result_sha256"], consumed_at=when)


def finish(model, req, *, recycle=True):
    assert model.apply(model.read(), "claim", "FETCHER", 101)
    assert model.apply(model.read(), "start", "FETCHER", 102)
    result = make_result(req)
    assert model.apply(model.read(), "result", "FETCHER", 103, result=result)
    assert model.apply(model.read(), "publish", "FETCHER", 104, readback_digest=result["result_sha256"])
    assert model.apply(model.read(), "ack", "COACH", 105, ack=ack_request(req, result))
    if recycle:
        assert model.apply(model.read(), "recycle", "WATCHDOG", 106)
    return result


def test_schema_export_transition_matrix_and_fixtures_are_exact_and_unreleased():
    spec = json.loads((ROOT / "protocol/drafts/r2-command-contract.json").read_text(encoding="utf-8"))
    assert spec["compatibility_status"] == "UNRELEASED"
    assert spec["schemas"] == SCHEMAS
    assert spec["transitions"] == {k:{"actor":v[0], "from":sorted(v[1])} for k,v in TRANSITIONS.items()}
    for schema in SCHEMAS.values():
        Draft202012Validator.check_schema(schema)
    fixtures = json.loads((ROOT / "protocol/drafts/r2-command-fixtures.json").read_text(encoding="utf-8"))
    for item in fixtures["positive"]:
        validate_shape(item["schema"], item["value"])
    for item in fixtures["negative"]:
        with pytest.raises(ContractError):
            validate_shape(item["schema"], item["value"])
    assert set(fixtures["legacy_mapping"]) == {"FETCH_BALL", "STOP_BALL", "WAKE_BONE", "DOG_PULSE", "WATCHDOG"}
    assert spec["installed_protocol_major"] == 1


def test_inline_bytes_and_artifact_exact_descriptor_are_verified_before_admission():
    assert validate(request(text="print('ž')"))
    req = request()
    req["payload"] = dict(kind="ARTIFACT", interpreter="python", size_bytes=1024,
                          slot="artifact.000.input", artifact_generation=8)
    descriptor = dict(generation=8, size_bytes=1024, sha256=req["payload_sha256"], target_id=TARGET, complete=True)
    assert validate(req, artifacts={"artifact.000.input":descriptor})
    for key, value in (("generation",7),("sha256","f"*64),("target_id",OTHER),("complete",False),("size_bytes",1023)):
        bad = {**descriptor, key:value}
        with pytest.raises(ContractError, match="ARTIFACT_UNVERIFIED"):
            validate(req, artifacts={"artifact.000.input":bad})


@pytest.mark.parametrize("key,value,code", [
    ("extra",True,"SCHEMA"),("target_id", "00000000-0000-4000-8000-000000000009","UNKNOWN_TARGET"),
    ("domain_id",OTHER,"WRONG_DOMAIN"),("generation",True,"SCHEMA"),("generation",1.0,"SCHEMA"),("generation",0,"SCHEMA"),
    ("generation",MAX_GENERATION+1,"SCHEMA"),("operation_id","a"*64,"IDENTITY"),
    ("protocol_major",1,"SCHEMA"),("protocol_minor",1,"SCHEMA"),
    ("payload_sha256","a"*64,"PAYLOAD_INTEGRITY"),("claim_deadline",100,"TIME_RANGE"),
    ("given_at",101,"FUTURE_REQUEST"),("run_limit_s",0,"SCHEMA")])
def test_autosniff_rejections_leave_target_unreserved(key,value,code):
    req = request(); req[key] = value
    model = AdmissionModel(DOMAIN,{TARGET})
    before = deepcopy(model.state)
    receipt = model.submit(encoded(req),now=100,ingress_slot=3,ingress_generation=7,ingress_revision="synthetic-r9")
    assert receipt["disposition"] == "REJECTED" and receipt["reason"] == code
    assert receipt["ingress_slot"] == 3 and receipt["ingress_generation"] == 7
    assert receipt["ingress_revision"] == "synthetic-r9"
    assert model.state == before


@pytest.mark.parametrize("raw", [b"{",b'[]',b'null',b'{"x":1,"x":2}',b'NaN',b'Infinity',b'\xff'])
def test_malformed_ingress_receipt_has_exact_raw_hash_without_reflecting_content(raw):
    receipt = AdmissionModel(DOMAIN,{TARGET}).submit(raw,now=100)
    assert receipt["disposition"] == "REJECTED"
    assert receipt["operation_id"] is None
    assert receipt["request_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["reason"] in {"MALFORMED", "SCHEMA"}


def test_invalid_transport_provenance_is_rejected_before_mutation():
    model = AdmissionModel(DOMAIN,{TARGET})
    before = deepcopy(model.state)
    with pytest.raises(ContractError):
        model.submit(encoded(request()),now=100,ingress_slot=16)
    assert model.state == before
    with pytest.raises(ContractError):
        model.submit("not bytes",now=100)
    assert model.state == before


def test_strict_decoding_and_unicode_errors_never_become_executable_requests():
    with pytest.raises(ContractError,match="TOO_LARGE"):
        decode_request(b"x"*1025)
    req = request(); req["payload"]["text"] = "\ud800"
    with pytest.raises(ContractError,match="PAYLOAD_INTEGRITY"):
        validate(req)
    req = request(text="é"*128); assert validate(req)
    req["payload"]["size_bytes"] = 128
    with pytest.raises(ContractError,match="PAYLOAD_INTEGRITY"):
        validate(req)


def test_restart_duplicate_expired_duplicate_conflict_and_busy_are_deterministic():
    model = AdmissionModel(DOMAIN,{TARGET,OTHER}); req = request()
    assert model.submit(encoded(req),now=100)["disposition"] == "ADMITTED"
    restarted = AdmissionModel(DOMAIN,{TARGET,OTHER},saved=model.state)
    assert restarted.submit(encoded(req),now=300)["disposition"] == "DUPLICATE"
    assert restarted.submit(encoded(request(text="print('changed')")),now=100)["reason"] == "ID_CONFLICT"
    assert restarted.submit(encoded(request(generation=2)),now=100)["reason"] == "BUSY"
    assert restarted.submit(encoded(request(target=OTHER)),now=100)["disposition"] == "ADMITTED"
    assert restarted.state[TARGET] == model.state[TARGET]


@pytest.mark.parametrize("case,reason", [("expiry","EXPIRED"),("gap","GENERATION_GAP"),("space","CAPACITY")])
def test_pre_admission_boundaries(case,reason):
    model = AdmissionModel(DOMAIN,{TARGET})
    req = request(generation=2 if case == "gap" else 1)
    receipt = model.submit(encoded(req),now=200 if case == "expiry" else 100,has_capacity=case != "space")
    assert receipt["reason"] == reason
    assert model.state[TARGET]["generation"] == 0


def test_retained_duplicate_then_bounded_history_eviction_cannot_reexecute_old_generation():
    model = AdmissionModel(DOMAIN,{TARGET})
    for generation in (1,2):
        req = request(generation=generation)
        assert model.submit(encoded(req),now=100)["disposition"] == "ADMITTED"
        lifecycle = LifecycleModel(req); finish(lifecycle,req)
        model.recycle(TARGET,lifecycle.read(),retain=1)
        assert model.submit(encoded(req),now=400)["disposition"] == "DUPLICATE"
    restored = AdmissionModel(DOMAIN,{TARGET},saved=model.state)
    assert restored.submit(encoded(request()),now=100)["reason"] == "STALE_GENERATION"
    assert len(restored.state[TARGET]["history"]) == 1


@pytest.mark.parametrize("key", list(binding(request())))
def test_result_and_ack_bind_all_correlation_fields(key):
    req = request(); model = LifecycleModel(req); result = make_result(req)
    wrong = deepcopy(result)
    value = wrong["binding"][key]
    wrong["binding"][key] = value + 1 if type(value) is int else (OTHER if key.endswith("_id") and key != "operation_id" else "f"*64)
    wrong["result_sha256"] = digest({k:v for k,v in wrong.items() if k != "result_sha256"})
    with pytest.raises(ContractError):
        validate_result(wrong,binding(req))
    assert model.apply(model.read(),"claim","FETCHER",101)
    assert model.apply(model.read(),"result","FETCHER",102,result=result)
    assert model.apply(model.read(),"publish","FETCHER",103,readback_digest=result["result_sha256"])
    ack = ack_request(req,result); ack["binding"] = wrong["binding"]
    with pytest.raises(ContractError):
        model.apply(model.read(),"ack","COACH",105,ack=ack)
    assert model.state["consumption"] == "PENDING"


@pytest.mark.parametrize("winner", ["claim","expire","withdraw"])
def test_claim_timeout_withdrawal_compete_on_same_snapshot(winner):
    req = request(); model = LifecycleModel(req)
    if winner == "withdraw":
        assert model.cancel(model.read(),cancel_request(req))
    snapshot = model.read()
    assert model.apply(snapshot,winner,"FETCHER" if winner == "claim" else "WATCHDOG",101 if winner != "expire" else 200)
    loser = "expire" if winner == "claim" else "claim"
    assert model.apply(snapshot,loser,"WATCHDOG" if loser == "expire" else "FETCHER",200) is False
    if winner == "claim":
        with pytest.raises(ContractError,match="TRANSITION"):
            model.apply(model.read(),"expire","WATCHDOG",300)
        assert model.apply(model.read(),"unknown","WATCHDOG",300)
        assert model.status()["execution"] == "UNKNOWN" and not model.status()["terminal"]
    else:
        assert model.status()["execution"] == "NOT_EXECUTED"
        assert model.state["result"]["effects"] == "NONE"


def test_deadline_equality_and_cancellation_first_prevent_fresh_claim():
    model = LifecycleModel(request())
    assert not model.apply(model.read(),"claim","FETCHER",200)
    assert not model.apply(model.read(),"expire","WATCHDOG",199)
    assert model.cancel(model.read(),cancel_request(request()))
    assert not model.apply(model.read(),"claim","FETCHER",101)


def test_receipt_execution_publication_ack_and_recycling_are_independent():
    req = request(); model = LifecycleModel(req)
    assert model.status()["receipt"] == "ADMITTED"
    assert not model.status()["terminal"] and model.status()["publication"] == "NONE"
    assert model.apply(model.read(),"claim","FETCHER",101)
    assert model.apply(model.read(),"start","FETCHER",102)
    assert model.status()["deadline_at"] == 132
    result = make_result(req)
    assert model.apply(model.read(),"result","FETCHER",103,result=result)
    assert model.status()["execution"] == "EXITED" and not model.status()["terminal"]
    for readback in (None,"a"*64):
        with pytest.raises(ContractError,match="PUBLICATION_UNCONFIRMED"):
            model.apply(model.read(),"publish","FETCHER",104,readback_digest=readback)
    assert model.apply(model.read(),"publish","FETCHER",104,readback_digest=result["result_sha256"])
    snapshot = model.read(); model.status(); assert model.read() == snapshot
    with pytest.raises(ContractError):
        model.apply(model.read(),"recycle","WATCHDOG",105)
    bad_ack = ack_request(req,result); bad_ack["result_sha256"] = "f"*64
    with pytest.raises(ContractError,match="ACK_MISMATCH"):
        model.apply(model.read(),"ack","COACH",105,ack=bad_ack)
    assert model.apply(model.read(),"ack","COACH",105,ack=ack_request(req,result))
    assert model.apply(model.read(),"recycle","WATCHDOG",106)
    assert model.state["history"]["result_sha256"] == result["result_sha256"]
    assert model.state["next_check_at"] is None and model.state["result"] is None


def test_cancel_ack_and_signal_do_not_prove_interruption_and_natural_exit_wins():
    req = request(); model = LifecycleModel(req)
    assert model.apply(model.read(),"claim","FETCHER",101)
    assert model.apply(model.read(),"start","FETCHER",102)
    for state, actor in (("REQUESTED","COACH"),("ACKNOWLEDGED","FETCHER"),("SIGNALLED","FETCHER")):
        assert model.cancel(model.read(),cancel_request(req,state),actor=actor)
        assert model.status()["execution"] == "RUNNING"
    with pytest.raises(ContractError,match="CANCEL_TRANSITION"):
        model.cancel(model.read(),cancel_request(req),actor="COACH")
    result = make_result(req)
    assert model.apply(model.read(),"result","FETCHER",103,result=result)
    assert model.cancel(model.read(),cancel_request(req,"ALREADY_FINISHED"),actor="FETCHER")
    assert model.state["result"]["outcome"] == "DONE"


@pytest.mark.parametrize("fields", [dict(outcome="CANCELLED"),dict(execution="INTERRUPTED"),
    dict(exit_code=None),dict(exit_code=1),dict(interruption_proven=True),dict(reason="INTERRUPTED"),
    dict(outcome="PARTIAL"),dict(execution="NOT_EXECUTED",outcome="FAILED",exit_code=None,reason="CLAIM_EXPIRED",effects="UNKNOWN")])
def test_false_success_interruption_and_nonexecution_are_rejected(fields):
    with pytest.raises(ContractError,match="RESULT_SEMANTICS"):
        make_result(request(),**fields)


@pytest.mark.parametrize("fields", [dict(),dict(outcome="FAILED",exit_code=1,reason="EXIT_NONZERO"),
    dict(outcome="PARTIAL",exit_code=1,reason="EXIT_NONZERO",effects="KNOWN"),
    dict(outcome="CANCELLED",execution="INTERRUPTED",interruption_proven=True,reason="INTERRUPTED",exit_code=None,effects="UNKNOWN"),
    dict(outcome="PARTIAL",execution="INTERRUPTED",interruption_proven=True,reason="INTERRUPTED",exit_code=-9,effects="KNOWN")])
def test_evidence_based_result_combinations(fields):
    result = make_result(request(),**fields)
    assert validate_result(result,binding(request())) == result
    result["stdout_tail"] = "tampered"
    with pytest.raises(ContractError,match="RESULT_INTEGRITY"):
        validate_result(result,binding(request()))


@pytest.mark.parametrize("event", list(TRANSITIONS))
def test_no_transition_is_available_to_unknown_actor(event):
    model = LifecycleModel(request()); before = model.read()
    with pytest.raises(ContractError,match="TRANSITION"):
        model.apply(before,event,"OTHER",101)
    assert model.read() == before


def test_waits_have_reason_deadline_next_check_and_unknown_does_not_reset_operation():
    model = LifecycleModel(request())
    for event, reason in (("wait_host","HOST"),("wait_fetcher","FETCHER")):
        assert model.apply(model.read(),event,"WATCHDOG",101)
        status = model.status()
        assert status["wait_reason"] == reason and status["deadline_at"] == 200
        assert status["next_check_at"] == 106
    assert model.apply(model.read(),"claim","FETCHER",102)
    assert model.apply(model.read(),"unknown","WATCHDOG",200)
    assert model.status()["wait_reason"] == "EXECUTION_UNKNOWN"
    assert model.status()["deadline_at"] is None
    assert model.apply(model.read(),"result","FETCHER",201,result=make_result(request()))
    assert model.status()["responsible"] == "FETCHER"


def test_compact_leaves_fit_rp009_budgets_roundtrip_and_refuse_old_generation():
    req = request(generation=MAX_GENERATION)
    req.update(given_at=999999999990,claim_deadline=999999999999)
    result = make_result(req,stdout_tail="x"*128,stderr_tail="y"*128,
                         artifact_output=dict(slot="artifact.063.output",generation=MAX_GENERATION,sha256="f"*64,size_bytes=8388608))
    for kind,value in (("result",result),("cancel",cancel_request(req)),("ack",ack_request(req,result))):
        record = compact_record(kind,value,binding(req),63)
        assert expand_leaf(kind,record,binding(req)) == value
        wrong = {**binding(req),"generation":MAX_GENERATION-1}
        with pytest.raises(ContractError,match="BINDING"):
            expand_leaf(kind,record,wrong)
    compact_record("status_projection",LifecycleModel(req).status(),binding(req),63)
    pack_record("ingress.015",req); pack_record("target.063.work",req)


def test_variable_width_encoding_never_silently_truncates_to_fit_slots():
    req = request(text="\x01"*256)
    with pytest.raises(ContractError,match="TOO_LARGE"):
        validate(req)
    result = make_result(request(),stdout_tail="\x01"*128,stderr_tail="\x01"*128)
    with pytest.raises(ContractError,match="TOO_LARGE"):
        compact_record("result",result,binding(request()),0)


def test_clock_regression_rejected_without_mutation():
    model = LifecycleModel(request()); before = model.read()
    for now in (99,True,-1,10**12+1):
        with pytest.raises(ContractError,match="TIME_RANGE"):
            model.apply(before,"claim","FETCHER",now)
        assert model.read() == before
