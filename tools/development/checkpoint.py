"""Prepare, publish and inspect public progress; never execute a recorded action.

Git uses existing noninteractive credentials. A connector may implement Backend
or use the same documented tree/commit/non-force-ref/readback transaction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Protocol

import yaml

from . import schemas
from .ledger import (JOURNAL, PLAN, RESUME, LedgerError, PublicCommits, _journals,
                     load, public_data, public_path, require, shape, validate,
                     validate_transitions)

MANIFEST = PLAN + "/manifest.yaml"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class Plan:
    branch: str
    expected_head: str
    event_id: str
    event_kind: str
    files: dict[str, str]

    @property
    def digest(self):
        return hashlib.sha256(canonical(asdict(self)).encode()).hexdigest()

    def check(self):
        require(re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", self.branch), "BRANCH_INVALID")
        shape(self.expected_head, schemas.SHA)
        require(self.event_kind in {"INTENT", "OUTCOME", "STARTED", "OBSERVATION", "CORRECTION", "RECONCILED", "BLOCKED"},
                "EVENT_KIND_INVALID")
        require(self.files and len(self.files) <= 256, "CHECKPOINT_SIZE_INVALID")
        require(all(isinstance(v, str) for v in self.files.values()), "CHECKPOINT_CONTENT_INVALID")
        require(sum(len(v.encode()) for v in self.files.values()) <= 2_000_000, "CHECKPOINT_SIZE_INVALID")
        for path, content in self.files.items():
            shape(path, schemas.PATH)
            require(path.startswith("docs/") and ".." not in path.split("/") and "\\" not in path
                    and ":" not in path and "//" not in path, "CHECKPOINT_PATH_INVALID")
            require(isinstance(content, str), "CHECKPOINT_CONTENT_INVALID")
            public_data(content)
        shape(self.event_id, {"type": "string", "pattern": r"^RP-\d{3}-A\d{3}-\d{4}$"})
        journals = [p for p in self.files if p.startswith(JOURNAL + "/")]
        require(len(journals) == 1, "CHECKPOINT_JOURNAL_REQUIRED")
        event = json.loads(self.files[journals[0]].splitlines()[-1])
        shape(event, schemas.EVENT)
        require(event["event_id"] == self.event_id and event["event"] == self.event_kind,
                "CHECKPOINT_EVENT_MISMATCH")


def project(root, manifest):
    """Only checkbox marks change; stable definitions and historical text survive."""
    files = {}
    index_path = PLAN + "/CHECKLIST.md"
    index = public_path(root, index_path).read_text(encoding="utf-8")
    for item, step in manifest["steps"].items():
        path = PLAN + "/" + step["definition"]
        before = public_path(root, path).read_text(encoding="utf-8")
        completed = set(step["completed_checks"])
        after = re.sub(r"^- \[[ x]\] \*\*(RP-\d{3}\.C\d+)\*\*",
                       lambda m: f"- [{'x' if m[1] in completed else ' '}] **{m[1]}**", before, flags=re.M)
        if after != before:
            files[path] = after
        index = re.sub(rf"^- \[[ x]\] (?=\[{re.escape(item)} -)",
                       f"- [{'x' if step['status'] == 'VERIFIED' else ' '}] ", index, flags=re.M)
    if index != public_path(root, index_path).read_text(encoding="utf-8"):
        files[index_path] = index
    return files


def _stage_public_inputs(root, staging, expected_head, reachable):
    """Retain original source references without staging private/untracked inputs."""
    shutil.copytree(root / "docs", staging / "docs", symlinks=True)
    events, _, _ = _journals(root, reachable)
    references = sorted({path for event in events.values() for path in event.get("evidence", [])
                         if path.startswith(("src/", "tests/", "tools/"))})
    backend = GitBackend(root)
    total = 0
    for path in references:
        local = public_path(root, path)
        entries = backend.run("ls-tree", "-z", expected_head, "--", path).split("\0")
        require(len(entries) == 2 and not entries[1] and "\t" in entries[0],
                "SOURCE_REFERENCE_NOT_PUBLIC_FILE")
        header, name = entries[0].split("\t", 1)
        fields = header.split()
        require(name == path and len(fields) == 3 and fields[0] in {"100644", "100755"}
                and fields[1] == "blob", "SOURCE_REFERENCE_NOT_PUBLIC_FILE")
        size = int(backend.run("cat-file", "-s", fields[2]))
        total += size
        require(0 <= size and total <= 2_000_000, "SOURCE_REFERENCE_INPUT_TOO_LARGE")
        try:
            blob = backend.run("cat-file", "blob", fields[2]).encode("utf-8")
        except UnicodeError:
            raise LedgerError("SOURCE_REFERENCE_UNSUPPORTED") from None
        require(local.read_bytes().replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n"),
                "SOURCE_REFERENCE_DIRTY")
        target = staging / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)


def prepare(root, event, branch, expected_head, *, manifest=None, evidence=None, defects=None,
            cursor_updates=None, reachable=None, base_verifier=None):
    root = Path(root).resolve()
    reachable = reachable or PublicCommits(root)
    (base_verifier or verify_checkout_base)(root, expected_head)
    validate(root, reachable=reachable)
    shape(event, schemas.EVENT)
    public_data(event)
    require(reachable(expected_head) and reachable(event["source_ref"]), "PUBLIC_COMMIT_MISSING")
    journal = f"{JOURNAL}/{event['item']}/{event['attempt']}/events.jsonl"
    existing = root / journal
    prefix = existing.read_text(encoding="utf-8") if existing.exists() else ""
    require(not prefix or prefix.endswith("\n"), "JOURNAL_NOT_APPENDABLE")
    files = {journal: prefix + canonical(event) + "\n"}
    old_manifest = load(root, MANIFEST)
    manifest = old_manifest if manifest is None else manifest
    shape(manifest, schemas.MANIFEST)
    validate_transitions(old_manifest, manifest)
    if manifest != old_manifest:
        files[MANIFEST] = yaml.safe_dump(manifest, sort_keys=False)
    from .defects import REGISTRY, validate_registry_history
    if defects is not None:
        validate_registry_history(load(root, REGISTRY), defects, old_manifest, manifest)
        files[REGISTRY] = yaml.safe_dump(defects, sort_keys=False)
    files.update(project(root, manifest))
    for path, content in (evidence or {}).items():
        require(path.startswith(f"{PLAN}/evidence/{event['item']}/{event['attempt']}/"), "EVIDENCE_OWNER_MISMATCH")
        require(not (root / path).exists(), "EVIDENCE_IMMUTABLE")
        files[path] = content
    cursor = load(root, RESUME)
    updates = cursor_updates or {}
    # Identity/pending fields are derived, never accepted from free-form overrides.
    allowed = {"last_completed", "verification", "expected_user_action", "blocking_decisions", "known_open_defects", "rollback"}
    require(updates.keys() <= allowed, "CURSOR_OVERRIDE_REJECTED")
    cursor.update(updates)
    cursor.update(work_item=event["item"], check=event["check"], attempt=event["attempt"],
                  phase=event["phase"], source_branch=branch, source_commit=event["source_ref"],
                  journal=journal, last_verified_event=event["event_id"], next_action=event["next_action"])
    # Candidate validation uses only public documentation, never installed state.
    with tempfile.TemporaryDirectory(prefix="tb4-ledger-") as tmp:
        staging = Path(tmp)
        _stage_public_inputs(root, staging, expected_head, reachable)
        for path, content in files.items():
            target = staging / path
            require(target.resolve().is_relative_to(staging.resolve()), "CHECKPOINT_PATH_INVALID")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        _, pending, _ = _journals(staging, reachable)
        cursor["unsettled_intents"] = sorted(pending)
        files[RESUME] = yaml.safe_dump(cursor, sort_keys=False)
        (staging / RESUME).write_text(files[RESUME], encoding="utf-8")
        validate(staging, reachable=reachable)
    plan = Plan(branch, expected_head, event["event_id"], event["event"], files)
    plan.check()
    return plan


class Backend(Protocol):
    def read_ref(self, branch: str) -> str: ...
    def create_commit(self, parent: str, files: Mapping[str, str], message: str) -> str: ...
    def update_ref(self, branch: str, expected: str, commit: str) -> None: ...
    def read_files(self, commit: str, paths: list[str]) -> dict[str, str]: ...


def validate_plan(root, plan, reachable=None, base_verifier=None):
    """Revalidate a serialized plan immediately before publication."""
    root = Path(root).resolve()
    plan.check()
    (base_verifier or verify_checkout_base)(root, plan.expected_head)
    reachable = reachable or PublicCommits(root)
    validate(root, reachable=reachable)
    require(reachable(plan.expected_head), "PUBLIC_COMMIT_MISSING")
    with tempfile.TemporaryDirectory(prefix="tb4-candidate-") as tmp:
        staging = Path(tmp)
        _stage_public_inputs(root, staging, plan.expected_head, reachable)
        for path, content in plan.files.items():
            target = staging / path
            require(target.resolve().is_relative_to(staging.resolve()), "CHECKPOINT_PATH_INVALID")
            if target.exists():
                previous = target.read_text(encoding="utf-8")
                if path.startswith(JOURNAL + "/"):
                    require(content.startswith(previous), "HISTORY_REWRITTEN")
                if path.startswith(PLAN + "/evidence/"):
                    require(content == previous, "EVIDENCE_IMMUTABLE")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        validate_transitions(load(root, MANIFEST), load(staging, MANIFEST))
        from .defects import REGISTRY, validate_registry_history
        validate_registry_history(load(root, REGISTRY), load(staging, REGISTRY), load(root, MANIFEST), load(staging, MANIFEST))
        validate(staging, reachable=reachable)


def save_pending(path, value):
    """Atomic replacement of this helper's own public-only pending record."""
    path = Path(path)
    public_data(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", delete=False) as tmp:
        tmp.write(canonical(value) + "\n")
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_path = Path(tmp.name)
    os.replace(temp_path, path)


def verified_readback(backend, plan, commit):
    require(backend.read_ref(plan.branch) == commit, "REMOTE_REF_MISMATCH")
    actual = backend.read_files(commit, list(plan.files))
    require(actual == plan.files, "REMOTE_CONTENT_MISMATCH")


def publish(plan, backend, pending_path, *, validator):
    plan.check()
    validator(plan)
    pending_path = Path(pending_path)
    require(not pending_path.exists(), "PENDING_RECORD_EXISTS_INSPECT_FIRST")
    pending = {"schema_version": 1, "plan": asdict(plan), "digest": plan.digest,
               "candidate_commit": None, "state": "PREPARED"}
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    with pending_path.open("x", encoding="utf-8") as initial:
        initial.write(canonical(pending) + "\n")
        initial.flush()
        os.fsync(initial.fileno())
    try:
        require(backend.read_ref(plan.branch) == plan.expected_head, "REMOTE_CONFLICT")
        candidate = backend.create_commit(plan.expected_head, plan.files, "Checkpoint " + plan.event_id)
        shape(candidate, schemas.SHA)
        pending.update(candidate_commit=candidate, state="COMMIT_CREATED")
        save_pending(pending_path, pending)
        backend.update_ref(plan.branch, plan.expected_head, candidate)
        verified_readback(backend, plan, candidate)
        pending["state"] = "VERIFIED"
        save_pending(pending_path, pending)
        # This is a fresh publication receipt, not an executable command/token.
        return {"state": "VERIFIED", "commit": candidate, "digest": plan.digest,
                "next": "RECORDED_ACTION_READY" if plan.event_kind == "INTENT" else "CHECKPOINT_RECORDED"}
    except Exception:
        # Transport exceptions may contain secrets. Never persist/echo them.
        pending["state"] = "UNKNOWN"
        save_pending(pending_path, pending)
        return {"state": "UNKNOWN", "next": "INSPECT_PUBLICATION_NO_ACTION"}


def reconcile(pending_path, backend):
    """Inspect only. Never publish again, update a ref or execute a workload."""
    pending = json.loads(Path(pending_path).read_text(encoding="utf-8"))
    plan = Plan(**pending["plan"])
    plan.check()
    require(pending["digest"] == plan.digest, "PENDING_DIGEST_MISMATCH")
    try:
        head = backend.read_ref(plan.branch)
        if head == pending["candidate_commit"]:
            verified_readback(backend, plan, head)
            pending["state"] = "RECONCILED"
            save_pending(pending_path, pending)
            return {"state": "RECONCILED", "commit": head,
                    "next": "INSPECT_ACTION_EFFECTS" if plan.event_kind == "INTENT" else "CHECKPOINT_RECORDED"}
        if head == plan.expected_head:
            return {"state": "NOT_PUBLISHED", "next": "INSPECT_BEFORE_PUBLICATION_RETRY"}
        return {"state": "CONFLICT", "next": "INSPECT_REMOTE_HISTORY"}
    except Exception:
        return {"state": "UNKNOWN", "next": "INSPECT_PUBLICATION_NO_ACTION"}


def cold_resume(root, reachable=None):
    report = validate(root, reachable=reachable)
    cursor = load(Path(root), RESUME)
    return {"work_item": cursor["work_item"], "attempt": cursor["attempt"],
            "source_branch": cursor["source_branch"], "source_commit": cursor["source_commit"],
            "unsettled_intents": report["unsettled_intents"],
            "decision": "INSPECT_ACTION_EFFECTS" if report["unsettled_intents"] else "FOLLOW_RECORDED_NEXT_ACTION",
            "next_action": cursor["next_action"]}


class GitBackend:
    """Noninteractive Git; local working tree and index are never replaced."""
    def __init__(self, root):
        self.root = Path(root).resolve()

    def run(self, *args, data=None, extra_env=None):
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
        env.update(extra_env or {})
        p = subprocess.run(["git", "-C", str(self.root), *args], input=data,
                           capture_output=True, env=env, timeout=60)
        require(p.returncode == 0, "GIT_OPERATION_FAILED")
        return p.stdout.decode("utf-8")

    def read_ref(self, branch):
        require(re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", branch), "BRANCH_INVALID")
        rows = self.run("ls-remote", "origin", "refs/heads/" + branch).splitlines()
        require(len(rows) == 1, "REMOTE_REF_UNAVAILABLE")
        return rows[0].split()[0]

    def create_commit(self, parent, files, message):
        shape(parent, schemas.SHA)
        with tempfile.TemporaryDirectory(prefix="tb4-index-") as tmp:
            env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
            self.run("read-tree", parent, extra_env=env)
            for path, content in sorted(files.items()):
                blob = self.run("hash-object", "-w", "--stdin", data=content.encode()).strip()
                self.run("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", extra_env=env)
            tree = self.run("write-tree", extra_env=env).strip()
            return self.run("commit-tree", tree, "-p", parent, data=(message + "\n").encode()).strip()

    def update_ref(self, branch, expected, commit):
        require(self.read_ref(branch) == expected, "REMOTE_CONFLICT")
        shape(commit, schemas.SHA)
        # No force, force-with-lease or destructive worktree/index operations.
        self.run("push", "origin", commit + ":refs/heads/" + branch)

    def read_files(self, commit, paths):
        shape(commit, schemas.SHA)
        self.run("fetch", "origin", commit)
        return {p: self.run("show", commit + ":" + p) for p in paths}


def verify_checkout_base(root, expected_head):
    """A supplied ref must describe the actual local validation inputs."""
    backend = GitBackend(root)
    require(backend.run("rev-parse", "HEAD").strip() == expected_head, "CHECKOUT_BASE_MISMATCH")
    require(not backend.run("diff", "--name-only", expected_head, "--", "docs").strip(),
            "DOCUMENT_BASE_DIRTY")
    require(not backend.run("ls-files", "--others", "--exclude-standard", "--", "docs").strip(),
            "DOCUMENT_BASE_UNTRACKED")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--event", type=Path, required=True)
    prep.add_argument("--branch", required=True)
    prep.add_argument("--expected-head", required=True)
    prep.add_argument("--output", type=Path, required=True)
    pub = sub.add_parser("publish")
    pub.add_argument("--plan", type=Path, required=True)
    pub.add_argument("--pending", type=Path, required=True)
    rec = sub.add_parser("reconcile")
    rec.add_argument("--pending", type=Path, required=True)
    sub.add_parser("resume")
    args = p.parse_args(argv)
    try:
        if args.command == "prepare":
            event = json.loads(args.event.read_text(encoding="utf-8"))
            plan = prepare(args.root, event, args.branch, args.expected_head)
            require(not args.output.exists(), "OUTPUT_EXISTS")
            save_pending(args.output, asdict(plan))
            result = {"state": "PREPARED", "digest": plan.digest, "next": "PUBLISH_AND_VERIFY"}
        elif args.command == "publish":
            plan = Plan(**json.loads(args.plan.read_text(encoding="utf-8")))
            result = publish(plan, GitBackend(args.root), args.pending,
                             validator=lambda value: validate_plan(args.root, value))
        elif args.command == "reconcile":
            result = reconcile(args.pending, GitBackend(args.root))
        else:
            result = cold_resume(args.root)
        print(canonical(result))
        return 1 if result.get("state") in {"UNKNOWN", "CONFLICT", "NOT_PUBLISHED"} else 0
    except Exception as error:
        print(canonical({"state": "BLOCKED", "code": str(error) if isinstance(error, LedgerError) else "CHECKPOINT_INPUT_INVALID"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
