"""Read-only, fail-closed R2 progress validation. No publication or replay here."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from . import schemas

PLAN = "docs/implementation-plan/revisions/R2"
CURRENT = "docs/implementation-plan/CURRENT.yaml"
RESUME = "docs/development/RESUME.yaml"
JOURNAL = "docs/development/journal"


class LedgerError(ValueError):
    """Only an allowlisted diagnostic code; never echo invalid input values."""


def require(condition, code):
    if not condition:
        raise LedgerError(code)


def shape(value, schema):
    require(not next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), None),
            "RECORD_SCHEMA_INVALID")


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        require(isinstance(key, str) and key not in result, "DUPLICATE_OR_INVALID_KEY")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_OR_INVALID_KEY")
        result[key] = value
    return result


def public_path(root, relative):
    require(isinstance(relative, str) and not PurePosixPath(relative).is_absolute()
            and "\\" not in relative and ":" not in relative
            and all(p not in {"..", "."} for p in relative.split("/")), "UNSAFE_REFERENCE")
    candidate = root / relative
    require(candidate.resolve().is_relative_to(root.resolve()), "UNSAFE_REFERENCE")
    require(candidate.is_file(), "REFERENCE_MISSING")
    return candidate


def load(root, relative):
    path = public_path(root, relative)
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            return json.loads(text, object_pairs_hook=_json_pairs)
        return yaml.load(text, Loader=UniqueLoader)
    except (UnicodeError, yaml.YAMLError, json.JSONDecodeError):
        raise LedgerError("RECORD_PARSE_INVALID") from None


def public_data(value):
    # Import the existing scanner while also covering JSONL (which its file
    # extension list did not originally include). Diagnostics never echo values.
    from tb4.security import scan_text
    text = json.dumps(value, ensure_ascii=True)
    require(not scan_text("docs/development/record.json", text), "PUBLIC_DATA_REJECTED")
    require(not re.search(r"(?i)([A-Z]:\\\\|/home/|/Users/|Bearer\s+|https?://(?!github\.com/SKIPaBOLT-wtf/TB4(?:/|\b)))", text),
            "PUBLIC_DATA_REJECTED")


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    require(result.returncode == 0, "GIT_REFERENCE_UNAVAILABLE")
    return result.stdout


class PublicCommits:
    """Validate locally fetched origin reachability; never infer it from HEAD.

    The caller fetches before validation. Offline validation cannot establish
    current GitHub availability; publication readback remains a separate gate.
    """
    def __init__(self, root):
        self.root = root
        self.refs = git(root, "for-each-ref", "--format=%(refname)", "refs/remotes/origin/").splitlines()
        self.cache = {}

    def __call__(self, sha):
        if sha not in self.cache:
            exists = re.fullmatch(r"[0-9a-f]{40}", str(sha)) is not None
            if exists:
                exists = subprocess.run(["git", "-C", str(self.root), "cat-file", "-e", sha + "^{commit}"],
                                        capture_output=True).returncode == 0
            self.cache[sha] = bool(exists and any(
                subprocess.run(["git", "-C", str(self.root), "merge-base", "--is-ancestor", sha, ref],
                               capture_output=True).returncode == 0 for ref in self.refs))
        return self.cache[sha]


def validate_journal(events, item, attempt, reachable):
    by_id, pending, actions = {}, {}, set()
    previous_time = None
    for n, event in enumerate(events, 1):
        if item.startswith("RP-"):
            shape(event, schemas.EVENT)
            stamp = datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
            require(previous_time is None or stamp >= previous_time, "EVENT_TIME_REVERSED")
            previous_time = stamp
        public_data(event)
        identity = f"{item}-{attempt}-{n:04d}"
        require(event.get("event_id") == identity and event.get("sequence") == n,
                "EVENT_ORDER_OR_ID_INVALID")
        require(event.get("item") == item and event.get("attempt") == attempt, "EVENT_OWNER_MISMATCH")
        if "check" in event:
            require(event["check"].startswith(item + ".") or item == "PLAN-R2", "CHECK_OWNER_MISMATCH")
        source = event.get("source_ref", event.get("base_commit"))
        if source:
            require(reachable(source), "PUBLIC_COMMIT_MISSING")
        kind, related = event.get("event"), event.get("related_event")
        if kind == "INTENT":
            if item.startswith("RP-"):
                require(related is None and event["outcome"] == "PENDING" and event["observed"] is None,
                        "INTENT_PHASE_INVALID")
            action = event.get("action_id", identity)
            require(action not in actions, "ACTION_ID_REUSED")
            actions.add(action)
            pending[identity] = event
        elif kind in {"OUTCOME", "RECONCILED", "BLOCKED"}:
            require(related in pending, "OUTCOME_WITHOUT_PENDING_INTENT")
            original = pending[related]
            require(event.get("action_id") == original.get("action_id"), "ACTION_ID_MISMATCH")
            if item.startswith("RP-"):
                require(event["check"] == original["check"], "CHECK_OWNER_MISMATCH")
                require(event["outcome"] not in {"PENDING", "STARTED"}
                        and event["observed"], "OUTCOME_NOT_OBSERVED")
            # UNKNOWN/BLOCKED remain unsettled until an actual reconciliation.
            if event.get("outcome") not in {"UNKNOWN", "BLOCKED"}:
                del pending[related]
        elif kind == "STARTED":
            require(related in pending and event.get("run_id"), "STARTED_WITHOUT_RUN_OR_INTENT")
        elif kind == "CORRECTION":
            require(related in by_id and event.get("observed"), "CORRECTION_TARGET_MISSING")
        elif kind != "OBSERVATION":
            raise LedgerError("EVENT_KIND_INVALID")
        by_id[identity] = event
    return by_id, pending


def _journals(root, reachable):
    events, pending, tails = {}, {}, {}
    for path in sorted((root / JOURNAL).glob("*/A[0-9][0-9][0-9]/events.jsonl")):
        try:
            rows = [json.loads(line, object_pairs_hook=_json_pairs)
                    for line in path.read_text(encoding="utf-8").splitlines()]
        except (UnicodeError, json.JSONDecodeError):
            raise LedgerError("JOURNAL_PARSE_INVALID") from None
        require(rows, "JOURNAL_EMPTY")
        found, unsettled = validate_journal(rows, path.parent.parent.name, path.parent.name, reachable)
        require(not (events.keys() & found.keys()), "EVENT_DUPLICATE")
        events.update(found)
        pending.update(unsettled)
        tails[path.relative_to(root).as_posix()] = rows[-1]["event_id"]
        for row in rows:
            for reference in row.get("evidence", []):
                public_path(root, reference)
    return events, pending, tails


def validate_history(root, base, manifest):
    # Append-only means byte prefix, including failed observations/corrections.
    paths = git(root, "ls-tree", "-r", "--name-only", base, JOURNAL).splitlines()
    for relative in paths:
        old = subprocess.run(["git", "-C", str(root), "show", base + ":" + relative], capture_output=True)
        require(old.returncode == 0, "BASE_HISTORY_UNAVAILABLE")
        current = public_path(root, relative).read_bytes().replace(b"\r\n", b"\n")
        require(current.startswith(old.stdout.replace(b"\r\n", b"\n")), "HISTORY_REWRITTEN")
    old = yaml.load(git(root, "show", base + ":" + PLAN + "/manifest.yaml"), Loader=UniqueLoader)
    require(old["steps"].keys() <= manifest["steps"].keys(), "STABLE_STEP_REMOVED")
    validate_transitions(old, manifest)


def validate_transitions(old, manifest):
    """Shared by read-only history checks and prospective checkpoint staging."""
    require(old["steps"].keys() <= manifest["steps"].keys(), "STABLE_STEP_REMOVED")
    transitions = {"PLANNED": {"PLANNED", "IN_PROGRESS", "BLOCKED", "SUPERSEDED"},
                   "IN_PROGRESS": {"IN_PROGRESS", "BLOCKED", "VERIFIED", "SUPERSEDED"},
                   "BLOCKED": {"BLOCKED", "IN_PROGRESS", "SUPERSEDED"},
                   "VERIFIED": {"VERIFIED", "IN_PROGRESS", "BLOCKED", "SUPERSEDED"},
                   "SUPERSEDED": {"SUPERSEDED"}}
    for key, previous in old["steps"].items():
        current = manifest["steps"][key]
        require(current["status"] in transitions[previous["status"]], "STATUS_TRANSITION_INVALID")
        if previous["status"] == "VERIFIED" and current["status"] not in {"VERIFIED", "SUPERSEDED"}:
            require(current["active_attempt"] > previous["active_attempt"]
                    and current["revalidation_required"], "REOPEN_REQUIRES_NEW_ATTEMPT")


def validate(root, reachable=None, base=None):
    root = Path(root).resolve()
    reachable = reachable or PublicCommits(root)
    current = load(root, CURRENT)
    require(current.get("active_revision") == "R2" and current.get("manifest") == PLAN + "/manifest.yaml"
            and current.get("resume") == RESUME, "AUTHORITY_PATH_MISMATCH")
    manifest = load(root, current["manifest"])
    cursor = load(root, RESUME)
    shape(manifest, schemas.MANIFEST)
    shape(cursor, schemas.CURSOR)
    public_data(manifest)
    public_data(cursor)
    require(manifest["status_authority"] == current["manifest"], "AUTHORITY_PATH_MISMATCH")
    require(reachable(manifest["baseline_commit"]) and reachable(cursor["source_commit"]), "PUBLIC_COMMIT_MISSING")
    require(current.get("authorization") == manifest["authorization"], "AUTHORIZATION_MISMATCH")
    started = manifest["execution_started"]
    require(started == cursor["implementation_started"], "AUTHORIZATION_MISMATCH")
    if started:
        require(manifest["authorization"] == cursor["execution_authorization"] == "PUBLIC_IMPLEMENTATION_AUTHORIZED",
                "IMPLEMENTATION_UNAUTHORIZED")
    events, pending, tails = _journals(root, reachable)
    require(set(cursor["unsettled_intents"]) == set(pending), "CURSOR_UNSETTLED_MISMATCH")
    require(tails.get(cursor["journal"]) == cursor["last_verified_event"], "CURSOR_JOURNAL_MISMATCH")
    last = events[cursor["last_verified_event"]]
    require(last["item"] == cursor["work_item"] and last["attempt"] == cursor["attempt"], "CURSOR_OWNER_MISMATCH")
    if cursor["work_item"].startswith("RP-"):
        require(cursor["work_item"] == manifest["current_step"] and cursor.get("check") == last["check"],
                "CURSOR_STEP_MISMATCH")
    steps = manifest["steps"]
    require(manifest["current_step"] in steps, "CURRENT_STEP_MISSING")
    if cursor["work_item"].startswith("RP-"):
        require(cursor["attempt"] == steps[cursor["work_item"]]["active_attempt"] and
                cursor["journal"] == f"{JOURNAL}/{cursor['work_item']}/{cursor['attempt']}/events.jsonl",
                "CURSOR_ATTEMPT_MISMATCH")
    requirements = load(root, PLAN + "/requirements.yaml")["requirements"]
    visiting, visited = set(), set()

    def visit(key):
        require(key in steps and key not in visiting, "DEPENDENCY_MISSING_OR_CYCLE")
        if key in visited:
            return
        visiting.add(key)
        for dep in steps[key]["depends_on"]:
            visit(dep)
        visiting.remove(key)
        visited.add(key)

    index = public_path(root, PLAN + "/CHECKLIST.md").read_text(encoding="utf-8")
    index_rows = re.findall(r"^- \[([ x])\] \[(RP-\d{3}) -", index, re.M)
    require(len(index_rows) == len(steps) and {k for _, k in index_rows} == set(steps), "INDEX_STEP_MISMATCH")
    accepted = 0
    for key, step in steps.items():
        visit(key)
        require(step["definition"] == f"steps/{key}.md", "DEFINITION_OWNER_MISMATCH")
        definition = public_path(root, PLAN + "/" + step["definition"]).read_text(encoding="utf-8")
        rows = re.findall(r"^- \[([ x])\] \*\*(RP-\d{3}\.C\d+)\*\*", definition, re.M)
        checks = [check for _, check in rows]
        require(checks and len(checks) == len(set(checks)) and all(c.startswith(key + ".") for c in checks),
                "CHECK_DEFINITION_INVALID")
        require(all(e.get("check") in checks for e in events.values() if e["item"] == key),
                "EVENT_CHECK_NOT_DEFINED")
        completed = set(step["completed_checks"])
        require(completed <= set(checks) and completed == {c for mark, c in rows if mark == "x"}, "CHECK_PROJECTION_MISMATCH")
        require(set(step["check_evidence"]) == completed, "CHECK_EVIDENCE_MISMATCH")
        require((dict((k, m) for m, k in index_rows)[key] == "x") == (step["status"] == "VERIFIED"),
                "INDEX_STATUS_MISMATCH")
        if step["status"] == "PLANNED":
            require(not completed and not step["evidence"] and step["active_attempt"] is None, "PLANNED_HAS_ACCEPTANCE")
        else:
            require(step["active_attempt"] is not None, "ACTIVE_ATTEMPT_MISSING")
        if step["status"] in {"IN_PROGRESS", "VERIFIED"} or completed:
            require(all(steps[d]["status"] == "VERIFIED" for d in step["depends_on"]), "DEPENDENCY_NOT_VERIFIED")
        for requirement in step["requirements"]:
            require(requirement in requirements and key in requirements[requirement]["steps"], "REQUIREMENT_MAPPING_MISMATCH")
        for path in step["evidence"] + step["amendments"]:
            public_path(root, path)
        for check in completed:
            refs = step["check_evidence"][check]
            require(refs and set(refs) <= set(step["evidence"]), "CHECK_EVIDENCE_MISSING")
            for ref in refs:
                require(ref.startswith(f"{PLAN}/evidence/{key}/{step['active_attempt']}/") and ref.endswith(".json"),
                        "EVIDENCE_OWNER_MISMATCH")
                receipt = load(root, ref)
                shape(receipt, schemas.EVIDENCE)
                public_data(receipt)
                require((receipt["item"], receipt["check"], receipt["attempt"]) ==
                        (key, check, step["active_attempt"]), "EVIDENCE_OWNER_MISMATCH")
                require(receipt["result"] == "PASS" and receipt["reviewed"] and receipt["exit_code"] == 0,
                        "EVIDENCE_NOT_REVIEWED_PASS")
                require(reachable(receipt["source_ref"]), "PUBLIC_COMMIT_MISSING")
                intent, outcome = events.get(receipt["intent_event"], {}), events.get(receipt["outcome_event"], {})
                require(intent.get("event") == "INTENT" and outcome.get("related_event") == intent.get("event_id")
                        and outcome.get("event") in {"OUTCOME", "RECONCILED"} and outcome.get("outcome") == "PASS"
                        and outcome.get("source_ref") == receipt["source_ref"]
                        and outcome.get("item") == key and outcome.get("attempt") == step["active_attempt"],
                        "EVIDENCE_EVENT_MISMATCH")
                for artifact in receipt["artifacts"]:
                    public_path(root, artifact)
        if step["status"] == "VERIFIED":
            require(completed == set(checks) and not step["revalidation_required"], "VERIFIED_INCOMPLETE")
            require(not any(e["item"] == key for e in pending.values()), "VERIFIED_UNSETTLED")
            accepted += 1
    if base:
        validate_history(root, base, manifest)
    return {"revision": "R2", "steps": len(steps), "verified": accepted,
            "unsettled_intents": sorted(pending), "result": "PASS"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--base", help="Fetched public base SHA for history and transition checks")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(validate(args.root, base=args.base), sort_keys=True))
        return 0
    except (LedgerError, OSError, KeyError, TypeError, ValueError, RecursionError) as error:
        code = str(error) if isinstance(error, LedgerError) else "LEDGER_INPUT_INVALID"
        print(json.dumps({"result": "FAIL", "code": code}, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
