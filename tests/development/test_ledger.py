from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from tools.development.ledger import (
    CURRENT, JOURNAL, PLAN, RESUME, LedgerError, PublicCommits,
    load, main, public_data, public_path, validate, validate_history, validate_journal,
)

SHA = "a" * 40


def event(n=1, kind="INTENT", related=None, outcome="PENDING"):
    return dict(schema_version=1, event_id=f"RP-001-A001-{n:04d}", sequence=n,
                at="2026-09-30T18:00:00Z", item="RP-001", check="RP-001.C1",
                attempt="A001", phase="TEST", event=kind, action_id="CHECK-LEDGER",
                related_event=related, source_ref=SHA, scope="Synthetic ledger only",
                procedure="Validate synthetic ledger fixture", expected="Invalid acceptance rejected",
                observed=None if kind == "INTENT" else "Synthetic check observed",
                outcome=outcome, evidence=[], rollback="Discard synthetic fixture",
                next_action="Inspect the same pending action", uncertainty="No runtime coverage")


def save(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if name.endswith(".jsonl"):
        text = "".join(json.dumps(row) + "\n" for row in value)
    elif name.endswith(".json"):
        text = json.dumps(value)
    elif isinstance(value, str):
        text = value
    else:
        text = yaml.safe_dump(value, sort_keys=False)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def ledger(tmp_path):
    save(tmp_path, PLAN + "/defects.yaml", {"schema_version": 2, "defects": {}})
    step = dict(title="Fixture", status="IN_PROGRESS", definition="steps/RP-001.md",
                depends_on=[], requirements=["R19"], completed_checks=[], evidence=[],
                amendments=[], active_attempt="A001", check_evidence={}, revalidation_required=[])
    save(tmp_path, PLAN + "/manifest.yaml", dict(schema_version=1, revision="R2",
         status_authority=PLAN + "/manifest.yaml", baseline_commit=SHA,
         authorization="PUBLIC_IMPLEMENTATION_AUTHORIZED", current_step="RP-001", execution_started=True,
         statuses=["PLANNED", "IN_PROGRESS", "BLOCKED", "VERIFIED", "SUPERSEDED"], steps={"RP-001": step}))
    save(tmp_path, CURRENT, dict(active_revision="R2", manifest=PLAN + "/manifest.yaml", resume=RESUME,
                                authorization="PUBLIC_IMPLEMENTATION_AUTHORIZED"))
    save(tmp_path, PLAN + "/requirements.yaml", {"requirements": {"R19": {"steps": ["RP-001"]}}})
    save(tmp_path, PLAN + "/steps/RP-001.md", "\n".join(f"- [ ] **RP-001.C{i}** - Check {i}" for i in range(1, 5)))
    save(tmp_path, PLAN + "/CHECKLIST.md", "- [ ] [RP-001 - Fixture](steps/RP-001.md)\n")
    save(tmp_path, JOURNAL + "/RP-001/A001/events.jsonl", [event()])
    save(tmp_path, RESUME, dict(schema_version=1, revision="R2", work_item="RP-001", check="RP-001.C1",
         attempt="A001", phase="TEST", source_branch="work/rp-001-a001", source_commit=SHA,
         journal=JOURNAL + "/RP-001/A001/events.jsonl", last_verified_event="RP-001-A001-0001",
         next_action="Inspect pending action", verification="Compare exact fixture",
         execution_authorization="PUBLIC_IMPLEMENTATION_AUTHORIZED", runtime_actions_allowed=False,
         implementation_started=True, unsettled_intents=["RP-001-A001-0001"], expected_user_action=None,
         rollback="Discard fixture"))
    return tmp_path


def check(root):
    return validate(root, reachable=lambda s: s == SHA)


def update(root, path, change):
    data = load(root, path)
    change(data)
    save(root, path, data)


def accept(root):
    save(root, JOURNAL + "/RP-001/A001/events.jsonl", [event(), event(2, "OUTCOME", "RP-001-A001-0001", "PASS")])
    update(root, RESUME, lambda c: c.update(last_verified_event="RP-001-A001-0002", unsettled_intents=[]))
    step = load(root, PLAN + "/manifest.yaml")["steps"]["RP-001"]
    for i in range(1, 5):
        c = f"RP-001.C{i}"
        p = PLAN + f"/evidence/RP-001/A001/C{i}.json"
        save(root, p, dict(schema_version=1, item="RP-001", check=c, attempt="A001", source_ref=SHA,
             result="PASS", reviewed=True, review_method="Compare invariant and observed fixture results",
             procedure="Validate synthetic fixture", expected="Invalid records rejected", observed="Rejection observed",
             exit_code=0, platform_scope="Synthetic cross-platform files", negative_cases=["Invalid acceptance"],
             unverified_scope="No live deployment", privacy_review="PUBLIC_SAFE_REVIEWED", rollback="Discard fixture",
             intent_event="RP-001-A001-0001", outcome_event="RP-001-A001-0002", artifacts=[]))
        step["completed_checks"].append(c)
        step["evidence"].append(p)
        step["check_evidence"][c] = [p]
    step["status"] = "VERIFIED"
    update(root, PLAN + "/manifest.yaml", lambda m: m["steps"].update({"RP-001": step}))
    p = root / PLAN / "steps/RP-001.md"
    p.write_text(p.read_text().replace("[ ]", "[x]"))
    save(root, PLAN + "/CHECKLIST.md", "- [x] [RP-001 - Fixture](steps/RP-001.md)\n")


def test_unsettled_intent_is_valid_but_never_accepted(ledger):
    assert check(ledger)["unsettled_intents"] == ["RP-001-A001-0001"]
    assert check(ledger)["verified"] == 0


def test_complete_reviewed_evidence_is_accepted(ledger):
    accept(ledger)
    assert check(ledger)["verified"] == 1


@pytest.mark.parametrize("mutation,code", [
    (lambda m: m["steps"]["RP-001"].update(completed_checks=["RP-001.C1"]), "CHECK_PROJECTION_MISMATCH"),
    (lambda m: m["steps"]["RP-001"].update(active_attempt=None), "CURSOR_ATTEMPT_MISMATCH"),
    (lambda m: m["steps"]["RP-001"].update(depends_on=["RP-001"]), "DEPENDENCY_MISSING_OR_CYCLE"),
    (lambda m: m["steps"]["RP-001"].update(depends_on=["RP-999"]), "DEPENDENCY_MISSING_OR_CYCLE"),
    (lambda m: m.update(authorization="PLANNING_ONLY"), "AUTHORIZATION_MISMATCH"),
    (lambda m: m["steps"]["RP-001"].update(unknown_metadata="unreviewed"), "RECORD_SCHEMA_INVALID"),
])
def test_invalid_progress_rejected(ledger, mutation, code):
    update(ledger, PLAN + "/manifest.yaml", mutation)
    with pytest.raises(LedgerError, match=code):
        check(ledger)


@pytest.mark.parametrize("field,value,code", [
    ("reviewed", False, "EVIDENCE_NOT_REVIEWED_PASS"),
    ("result", "FAIL", "EVIDENCE_NOT_REVIEWED_PASS"),
    ("exit_code", 1, "EVIDENCE_NOT_REVIEWED_PASS"),
    ("source_ref", "b" * 40, "PUBLIC_COMMIT_MISSING"),
    ("outcome_event", "RP-001-A001-0999", "EVIDENCE_EVENT_MISMATCH"),
    ("attempt", "A002", "EVIDENCE_OWNER_MISMATCH"),
])
def test_bad_evidence_never_verifies(ledger, field, value, code):
    accept(ledger)
    update(ledger, PLAN + "/evidence/RP-001/A001/C1.json", lambda e: e.update({field: value}))
    with pytest.raises(LedgerError, match=code):
        check(ledger)


def test_missing_receipt_rejected(ledger):
    accept(ledger)
    (ledger / PLAN / "evidence/RP-001/A001/C1.json").unlink()
    with pytest.raises(LedgerError, match="REFERENCE_MISSING"):
        check(ledger)


def test_unaccepted_dependency_rejected(ledger):
    def change(m):
        dep = copy.deepcopy(m["steps"]["RP-001"])
        dep.update(status="PLANNED", active_attempt=None, definition="steps/RP-002.md")
        m["steps"]["RP-002"] = dep
        m["steps"]["RP-001"]["depends_on"] = ["RP-002"]
    update(ledger, PLAN + "/manifest.yaml", change)
    with (ledger / PLAN / "CHECKLIST.md").open("a") as f:
        f.write("- [ ] [RP-002 - Dependency](steps/RP-002.md)\n")
    with pytest.raises(LedgerError, match="DEPENDENCY_NOT_VERIFIED"):
        check(ledger)


@pytest.mark.parametrize("change,code", [
    (dict(unsettled_intents=[]), "CURSOR_UNSETTLED_MISMATCH"),
    (dict(last_verified_event="RP-001-A001-9999"), "CURSOR_JOURNAL_MISMATCH"),
    (dict(check="RP-001.C2"), "CURSOR_STEP_MISMATCH"),
    (dict(source_commit="b" * 40), "PUBLIC_COMMIT_MISSING"),
])
def test_cursor_disagreement(ledger, change, code):
    update(ledger, RESUME, lambda c: c.update(change))
    with pytest.raises(LedgerError, match=code):
        check(ledger)


def test_duplicate_and_out_of_order_events():
    for rows in ([event(), event()], [event(2)]):
        with pytest.raises(LedgerError, match="EVENT_ORDER_OR_ID_INVALID"):
            validate_journal(rows, "RP-001", "A001", lambda _: True)


def corrected_started():
    intent = event()
    started = event(2, "STARTED", "RP-001-A001-0002")
    started["run_id"] = "synthetic-run-1"
    correction = event(3, "CORRECTION", started["event_id"], "RECORDED")
    correction.update(run_id=started["run_id"], reference_correction={
        "field":"related_event", "old_value":started["related_event"], "new_value":intent["event_id"]})
    return [intent, started, correction]


def test_started_reference_correction_preserves_original_and_pending_intent():
    rows = corrected_started(); original = copy.deepcopy(rows)
    with pytest.raises(LedgerError, match="STARTED_WITHOUT_RUN_OR_INTENT"):
        validate_journal(rows[:2], "RP-001", "A001", lambda _: True)
    by_id, pending = validate_journal(rows, "RP-001", "A001", lambda _: True)
    assert rows == original
    assert by_id[rows[1]["event_id"]]["related_event"] == rows[1]["event_id"]
    assert list(pending) == [rows[0]["event_id"]]
    rows.append(event(4, "OUTCOME", rows[0]["event_id"], "FAIL"))
    assert validate_journal(rows, "RP-001", "A001", lambda _: True)[1] == {}


@pytest.mark.parametrize("malformed", [None, [], "invalid", 1, {"event_id":{}}, {"event_id":[]}])
def test_correction_prepass_uses_schema_diagnostics_for_malformed_records(malformed):
    with pytest.raises(LedgerError,match="RECORD_SCHEMA_INVALID"):
        validate_journal([malformed], "RP-001", "A001", lambda _: True)


@pytest.mark.parametrize("fault", ["outcome", "target", "old", "new", "field", "run", "action", "check", "source", "no-justification", "not-correction", "extra-field"])
def test_reference_correction_cannot_rewrite_execution_or_invent_authorization(fault):
    rows = corrected_started(); c = rows[-1]; patch = c["reference_correction"]
    if fault == "outcome": c["outcome"] = "PASS"
    elif fault == "target": c["related_event"] = rows[0]["event_id"]
    elif fault == "old": patch["old_value"] = "different"
    elif fault == "new": patch["new_value"] = "RP-001-A001-9999"
    elif fault == "field": patch["field"] = "source_ref"
    elif fault == "run": c["run_id"] = "different"
    elif fault == "action": c["action_id"] = "DIFFERENT"
    elif fault == "check": c["check"] = "RP-001.C2"
    elif fault == "source": c["source_ref"] = "b" * 40
    elif fault == "no-justification": c["observed"] = None
    elif fault == "not-correction": c["event"] = "OBSERVATION"
    elif fault == "extra-field": patch["authorization"] = True
    with pytest.raises(LedgerError):
        validate_journal(rows, "RP-001", "A001", lambda _: True)


def test_duplicate_reference_correction_fails_even_when_same_value():
    rows = corrected_started(); duplicate = copy.deepcopy(rows[-1])
    duplicate.update(sequence=4, event_id="RP-001-A001-0004")
    with pytest.raises(LedgerError,match="REFERENCE_CORRECTION_CONFLICT"):
        validate_journal(rows+[duplicate], "RP-001", "A001", lambda _: True)


def test_correction_cannot_reopen_an_intent_closed_before_the_original_start():
    rows = corrected_started()
    outcome = event(2, "OUTCOME", rows[0]["event_id"], "FAIL")
    rows[1].update(sequence=3,event_id="RP-001-A001-0003",related_event="RP-001-A001-0003")
    rows[2].update(sequence=4,event_id="RP-001-A001-0004",related_event=rows[1]["event_id"])
    rows[2]["reference_correction"]["old_value"] = rows[1]["event_id"]
    with pytest.raises(LedgerError,match="STARTED_WITHOUT_RUN_OR_INTENT"):
        validate_journal([rows[0],outcome,*rows[1:]], "RP-001", "A001", lambda _: True)


def test_later_intent_cannot_retroactively_authorize_started():
    rows = corrected_started()
    rows[0].update(sequence=2,event_id="RP-001-A001-0002")
    rows[1].update(sequence=1,event_id="RP-001-A001-0001",related_event=None)
    rows[2].update(related_event=rows[1]["event_id"])
    rows[2]["reference_correction"].update(old_value=None,new_value=rows[0]["event_id"])
    with pytest.raises(LedgerError,match="REFERENCE_CORRECTION_TARGET_INVALID"):
        validate_journal([rows[1],rows[0],rows[2]], "RP-001", "A001", lambda _: True)


def test_failed_outcome_preserved_with_correction():
    rows = [event(), event(2, "OUTCOME", "RP-001-A001-0001", "FAIL"),
            event(3, "CORRECTION", "RP-001-A001-0002", "RECORDED")]
    found, pending = validate_journal(rows, "RP-001", "A001", lambda _: True)
    assert not pending and found["RP-001-A001-0002"]["outcome"] == "FAIL"


def test_unknown_effect_stays_pending_until_reconciled():
    rows = [event(), event(2, "OUTCOME", "RP-001-A001-0001", "UNKNOWN")]
    assert validate_journal(rows, "RP-001", "A001", lambda _: True)[1]
    rows.append(event(3, "RECONCILED", "RP-001-A001-0001", "PASS"))
    assert not validate_journal(rows, "RP-001", "A001", lambda _: True)[1]


def test_duplicate_outcome_and_orphan_correction_rejected():
    for rows, code in [([event(), event(2, "OUTCOME", "RP-001-A001-0001", "PASS"),
                        event(3, "OUTCOME", "RP-001-A001-0001", "PASS")], "OUTCOME_WITHOUT_PENDING_INTENT"),
                       ([event(1, "CORRECTION", "absent", "RECORDED")], "CORRECTION_TARGET_MISSING")]:
        with pytest.raises(LedgerError, match=code):
            validate_journal(rows, "RP-001", "A001", lambda _: True)


def test_unknown_commit_and_unallowlisted_fields():
    with pytest.raises(LedgerError, match="PUBLIC_COMMIT_MISSING"):
        validate_journal([event()], "RP-001", "A001", lambda _: False)
    row = event()
    row["raw_config"] = "synthetic canary"
    with pytest.raises(LedgerError, match="RECORD_SCHEMA_INVALID"):
        validate_journal([row], "RP-001", "A001", lambda _: True)


@pytest.mark.parametrize("changes", [dict(outcome="PASS"), dict(related_event="unrelated"), dict(observed="invented")])
def test_intent_cannot_invent_observation(changes):
    row = event()
    row.update(changes)
    with pytest.raises(LedgerError, match="INTENT_PHASE_INVALID"):
        validate_journal([row], "RP-001", "A001", lambda _: True)


def test_event_timestamp_reversal_rejected():
    outcome = event(2, "OUTCOME", "RP-001-A001-0001", "PASS")
    outcome["at"] = "2026-09-29T18:00:00Z"
    with pytest.raises(LedgerError, match="EVENT_TIME_REVERSED"):
        validate_journal([event(), outcome], "RP-001", "A001", lambda _: True)


def relocated_intent_note():
    intent = event()
    intent["observed"] = "Prior diagnostic fact; this action has not run."
    correction = event(2, "CORRECTION", intent["event_id"], "RECORDED")
    correction.update(observed=intent["observed"], intent_note_correction={
        "field": "observed", "old_value": intent["observed"], "new_value": None})
    return [intent, correction]


def test_intent_note_relocation_preserves_bytes_and_unsettled_action():
    rows = relocated_intent_note(); before = copy.deepcopy(rows)
    found, pending = validate_journal(rows, "RP-001", "A001", lambda _: True)
    assert rows == before and found[rows[0]["event_id"]] is rows[0]
    assert list(pending) == [rows[0]["event_id"]]
    assert found[rows[0]["event_id"]]["observed"] == rows[-1]["observed"]


@pytest.mark.parametrize("fault", ["old-text", "new-text", "field", "extra-field",
    "missing-note", "changed-note", "wrong-kind", "success", "target-outcome",
    "target-related", "target-kind", "missing-target", "action", "check", "source",
    "attempt", "item", "duplicate", "later-target", "mixed-correction"])
def test_note_correction_cannot_rewrite_facts_or_authorization(fault):
    rows = relocated_intent_note(); first, last = rows
    patch = last["intent_note_correction"]
    if fault == "old-text": patch["old_value"] = "Different fact"
    elif fault == "new-text": patch["new_value"] = "Approved"
    elif fault == "field": patch["field"] = "outcome"
    elif fault == "extra-field": patch["approval"] = True
    elif fault == "missing-note": first["observed"] = None
    elif fault == "changed-note": last["observed"] = "Different fact"
    elif fault == "wrong-kind": last["event"] = "OBSERVATION"
    elif fault == "success": last["outcome"] = "PASS"
    elif fault == "target-outcome": first["outcome"] = "PASS"
    elif fault == "target-related": first["related_event"] = "unrelated"
    elif fault == "target-kind": first["event"] = "OBSERVATION"
    elif fault == "missing-target": last["related_event"] = "missing"
    elif fault == "action": last["action_id"] = "OTHER-ACTION"
    elif fault == "check": last["check"] = "RP-001.C2"
    elif fault == "source": last["source_ref"] = "b" * 40
    elif fault == "attempt": last["attempt"] = "A002"
    elif fault == "item": last["item"] = "RP-002"
    elif fault == "duplicate":
        duplicate = copy.deepcopy(last)
        duplicate.update(sequence=3, event_id="RP-001-A001-0003")
        rows.append(duplicate)
    elif fault == "later-target": rows.reverse()
    elif fault == "mixed-correction":
        last["reference_correction"] = dict(field="related_event", old_value=None, new_value=first["event_id"])
    with pytest.raises(LedgerError):
        validate_journal(rows, "RP-001", "A001", lambda _: True)


@pytest.mark.parametrize("outcome", ["FAIL", "UNKNOWN"])
def test_note_correction_does_not_change_actual_outcome(outcome):
    rows = relocated_intent_note()
    actual = event(2, "OUTCOME", rows[0]["event_id"], outcome)
    rows[-1].update(sequence=3, event_id="RP-001-A001-0003")
    rows.insert(1, actual)
    found, pending = validate_journal(rows, "RP-001", "A001", lambda _: True)
    assert found[actual["event_id"]]["outcome"] == outcome
    assert bool(pending) == (outcome == "UNKNOWN")


def test_note_correction_still_requires_public_original_source():
    with pytest.raises(LedgerError, match="PUBLIC_COMMIT_MISSING"):
        validate_journal(relocated_intent_note(), "RP-001", "A001", lambda _: False)


def test_cursor_active_attempt_must_match(ledger):
    update(ledger, PLAN + "/manifest.yaml", lambda m: m["steps"]["RP-001"].update(active_attempt="A002"))
    with pytest.raises(LedgerError, match="CURSOR_ATTEMPT_MISMATCH"):
        check(ledger)


def test_event_check_must_exist_in_definition(ledger):
    row = event()
    row["check"] = "RP-001.C99"
    save(ledger, JOURNAL + "/RP-001/A001/events.jsonl", [row])
    update(ledger, RESUME, lambda c: c.update(check="RP-001.C99"))
    with pytest.raises(LedgerError, match="EVENT_CHECK_NOT_DEFINED"):
        check(ledger)


def test_status_authority_must_match_current(ledger):
    update(ledger, PLAN + "/manifest.yaml", lambda m: m.update(status_authority="docs/other.yaml"))
    with pytest.raises(LedgerError, match="AUTHORITY_PATH_MISMATCH"):
        check(ledger)


def test_public_data_canary_not_echoed():
    canary = "gh" + "p_" + "CANARY" * 5
    with pytest.raises(LedgerError) as caught:
        public_data({"observed": canary})
    assert str(caught.value) == "PUBLIC_DATA_REJECTED" and canary not in str(caught.value)


@pytest.mark.parametrize("path", ["../outside", "/absolute", "docs/../outside", "docs/x:stream", "docs\\outside"])
def test_reference_cannot_escape(path, tmp_path):
    with pytest.raises(LedgerError, match="UNSAFE_REFERENCE"):
        public_path(tmp_path, path)


def test_duplicate_yaml_and_json_keys_rejected(ledger):
    for name, body in [("docs/duplicate.yaml", "x: one\nx: two\n"), ("docs/duplicate.json", '{"x":1,"x":2}')]:
        save(ledger, name, body) if name.endswith("yaml") else (ledger / name).write_text(body)
        with pytest.raises(LedgerError, match="DUPLICATE_OR_INVALID_KEY"):
            load(ledger, name)


def git_fixture(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_unpublished_commit_is_not_public(ledger):
    git_fixture(ledger, "init")
    git_fixture(ledger, "add", ".")
    git_fixture(ledger, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
    sha = git_fixture(ledger, "rev-parse", "HEAD")
    assert not PublicCommits(ledger)(sha)
    git_fixture(ledger, "update-ref", "refs/remotes/origin/main", sha)
    assert PublicCommits(ledger)(sha)
    assert not PublicCommits(ledger)("b" * 40)


def test_history_rewrite_rejected_and_append_allowed(ledger):
    git_fixture(ledger, "init")
    git_fixture(ledger, "add", ".")
    git_fixture(ledger, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
    sha = git_fixture(ledger, "rev-parse", "HEAD")
    manifest = load(ledger, PLAN + "/manifest.yaml")
    save(ledger, JOURNAL + "/RP-001/A001/events.jsonl", [event(), event(2, "OUTCOME", "RP-001-A001-0001", "FAIL")])
    validate_history(ledger, sha, manifest)
    altered = event()
    altered["expected"] = "Rewritten history"
    save(ledger, JOURNAL + "/RP-001/A001/events.jsonl", [altered])
    with pytest.raises(LedgerError, match="HISTORY_REWRITTEN"):
        validate_history(ledger, sha, manifest)


def test_cli_failure_does_not_dump_invalid_input(tmp_path, capsys):
    assert main(["--root", str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)["result"] == "FAIL"


def test_progress_ci_does_not_build_installers():
    root = Path(__file__).resolve().parents[2]
    progress = (root / ".github/workflows/progress.yml").read_text()
    assert "build_desktop" not in progress and "fetch-depth: 0" in progress
    desktop = (root / ".github/workflows/desktop.yml").read_text()
    # Selection of code paths, with no broad docs match, keeps pure ledger
    # checkpoints out of the heavyweight installer workflow.
    assert "paths:" in desktop and "'docs/**'" not in desktop

def corrected_started_metadata():
    intent=event()
    started=event(2,"STARTED",intent["event_id"],"RUNNING")
    started.pop("run_id",None)
    started["observed"]="Local session 1234 is running; result remains unknown."
    correction=event(3,"CORRECTION",started["event_id"],"RECORDED")
    correction.update(observed=started["observed"],started_metadata_correction={
        "old_outcome":"RUNNING","new_outcome":"PENDING","old_run_id":None,"new_run_id":"Local session 1234"})
    return [intent,started,correction]

def test_started_metadata_correction_preserves_original_bytes_and_pending():
    rows=corrected_started_metadata();before=copy.deepcopy(rows)
    found,pending=validate_journal(rows,"RP-001","A001",lambda _:True)
    assert rows==before and found[rows[1]["event_id"]] is rows[1]
    assert found[rows[1]["event_id"]]["outcome"]=="RUNNING"
    assert list(pending)==[rows[0]["event_id"]]

@pytest.mark.parametrize("fault",["target-kind","target-outcome","existing-run","invented-run",
    "missing-observed","changed-observed","source","action","check","item","attempt",
    "success","new-success","old-run","extra","mixed","duplicate","missing","later","closed"])
def test_started_metadata_correction_cannot_invent_execution_or_success(fault):
    rows=corrected_started_metadata();first,target,last=rows
    patch=last["started_metadata_correction"]
    if fault=="target-kind":target["event"]="OUTCOME"
    elif fault=="target-outcome":target["outcome"]="FAIL"
    elif fault=="existing-run":target["run_id"]="earlier"
    elif fault=="invented-run":patch["new_run_id"]="Another session"
    elif fault=="missing-observed":target["observed"]=None
    elif fault=="changed-observed":last["observed"]="Invented launch"
    elif fault=="source":last["source_ref"]="b"*40
    elif fault=="action":last["action_id"]="OTHER"
    elif fault=="check":last["check"]="RP-001.C2"
    elif fault=="item":last["item"]="RP-002"
    elif fault=="attempt":last["attempt"]="A002"
    elif fault=="success":last["outcome"]="PASS"
    elif fault=="new-success":patch["new_outcome"]="PASS"
    elif fault=="old-run":patch["old_run_id"]="hidden"
    elif fault=="extra":patch["authorized"]=True
    elif fault=="mixed":
        last["intent_note_correction"]=dict(field="observed",old_value="x",new_value=None)
    elif fault=="duplicate":
        duplicate=copy.deepcopy(last);duplicate.update(sequence=4,event_id="RP-001-A001-0004")
        rows.append(duplicate)
    elif fault=="missing":last["related_event"]="missing"
    elif fault=="later":rows.reverse()
    elif fault=="closed":first.update(event="OUTCOME",related_event="missing",outcome="PASS")
    with pytest.raises(LedgerError):validate_journal(rows,"RP-001","A001",lambda _:True)

def corrected_action_case(outcome="FAIL"):
    first = event()
    first["action_id"] = "check-ledger"
    actual = event(2, "OUTCOME", first["event_id"], outcome)
    actual["action_id"] = first["action_id"]
    correction = event(3, "CORRECTION", first["event_id"], "RECORDED")
    correction["action_case_correction"] = dict(old_value="check-ledger", new_value="CHECK-LEDGER")
    return [first, actual, correction]


@pytest.mark.parametrize("outcome", ["PASS", "FAIL", "UNKNOWN", "BLOCKED"])
def test_action_case_correction_preserves_original_bytes_and_outcomes(outcome):
    rows = corrected_action_case(outcome)
    before = copy.deepcopy(rows)
    found, pending = validate_journal(rows, "RP-001", "A001", lambda _: True)
    assert rows == before and all(found[r["event_id"]] is r for r in rows)
    assert found[rows[1]["event_id"]]["outcome"] == outcome
    assert bool(pending) == (outcome in {"UNKNOWN", "BLOCKED"})


@pytest.mark.parametrize("fault", ["rename", "already-upper", "unicode", "target-kind",
    "target-missing", "source", "check", "scope", "item", "attempt", "action", "success",
    "extra", "mixed", "duplicate", "collision", "future-lowercase", "group-owner",
    "other-invalid-field", "case-mismatch"])
def test_action_case_correction_cannot_change_identity_or_authority(fault):
    rows = corrected_action_case()
    first, actual, last = rows
    patch = last["action_case_correction"]
    if fault == "rename": patch["new_value"] = "NEW-ACTION"
    elif fault == "already-upper": patch["old_value"] = "CHECK-LEDGER"
    elif fault == "unicode": patch["old_value"] = "café"
    elif fault == "target-kind": first["event"] = "OBSERVATION"
    elif fault == "target-missing": last["related_event"] = "missing"
    elif fault in {"source", "check", "scope", "item", "attempt", "action"}:
        key, value = {"source": ("source_ref", "b" * 40), "check": ("check", "RP-001.C2"),
            "scope": ("scope", "Wider scope"), "item": ("item", "RP-002"),
            "attempt": ("attempt", "A002"), "action": ("action_id", "OTHER")}[fault]
        last[key] = value
    elif fault == "success": last["outcome"] = "PASS"
    elif fault == "extra": patch["authorized"] = True
    elif fault == "mixed":
        last["intent_note_correction"] = dict(field="observed", old_value="invented", new_value=None)
    elif fault == "duplicate":
        duplicate = copy.deepcopy(last)
        duplicate.update(sequence=4, event_id="RP-001-A001-0004")
        rows.append(duplicate)
    elif fault == "collision": actual["action_id"] = "CHECK-LEDGER"
    elif fault == "future-lowercase":
        future = event(4, "OBSERVATION", first["event_id"], "RECORDED")
        future["action_id"] = "check-ledger"
        rows.append(future)
    elif fault == "group-owner": actual["item"] = "RP-002"
    elif fault == "other-invalid-field": actual["outcome"] = "INVENTED"
    elif fault == "case-mismatch": actual["action_id"] = "another-action"
    with pytest.raises(LedgerError):
        validate_journal(rows, "RP-001", "A001", lambda _: True)


def test_lowercase_action_still_invalid_without_explicit_correction():
    with pytest.raises(LedgerError, match="RECORD_SCHEMA_INVALID"):
        validate_journal(corrected_action_case()[:-1], "RP-001", "A001", lambda _: True)


def test_action_case_correction_requires_reachable_original_source():
    with pytest.raises(LedgerError, match="PUBLIC_COMMIT_MISSING"):
        validate_journal(corrected_action_case(), "RP-001", "A001", lambda _: False)
