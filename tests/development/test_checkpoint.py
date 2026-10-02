from __future__ import annotations

import copy
import json
import shutil

import pytest

from tests.development.test_ledger import SHA, accept, event, git_fixture, ledger, save
from tools.development.checkpoint import (GitBackend, Plan, cold_resume, main, prepare as real_prepare,
                                          publish, reconcile, validate_plan as real_validate_plan,
                                          verify_checkout_base)
from tools.development.ledger import JOURNAL, PLAN, RESUME, LedgerError, load, validate


def fixture_base(root, expected):
    # Pure ledger fixtures deliberately have no Git history. The native adapter
    # tests below exercise the real checkout identity guard.
    if (root / ".git").exists():
        verify_checkout_base(root, expected)


def source_reference_fixture(root):
    from tests.development.test_source_evidence_correction import rows
    history = rows()
    for path in ('src/tb4/synthetic.py', 'tests/test_synthetic.py'):
        save(root, path, 'synthetic = True\n')
    for path in ('docs/synthetic.md', 'docs/source-receipt.md'):
        save(root, path, 'Synthetic public source checkpoint\n')
    save(root, JOURNAL+'/RP-001/A001/events.jsonl', history)
    cursor = load(root, RESUME)
    cursor.update(last_verified_event=history[-1]['event_id'], unsettled_intents=[])
    save(root, RESUME, cursor)
    assert validate(root, reachable=lambda _: True)['verified'] == 0
    git_fixture(root, 'init')
    git_fixture(root, 'add', '.')
    git_fixture(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                'commit', '-m', 'synthetic public source references')
    next_event = event(4)
    next_event['action_id'] = 'CHECK-SOURCE-STAGING'
    return git_fixture(root, 'rev-parse', 'HEAD'), next_event


def test_source_reference_history_survives_prepare_revalidate_and_readback(ledger, tmp_path):
    head, row = source_reference_fixture(ledger)
    before = (ledger/JOURNAL/'RP-001/A001/events.jsonl').read_bytes()
    from tools.development.checkpoint import GitBackend
    public_prefix = GitBackend(ledger).run('show', head+':'+JOURNAL+'/RP-001/A001/events.jsonl')
    plan = prepare(ledger, row, 'work/fixture', head, reachable=lambda _: True)
    validate_plan(ledger, plan, reachable=lambda _: True)
    assert plan.files[JOURNAL+'/RP-001/A001/events.jsonl'].startswith(public_prefix)
    assert all(path.startswith('docs/') for path in plan.files)
    remote = Remote()
    remote.head = head
    assert send(ledger, plan, remote, tmp_path/'source-reference-pending.json')['state'] == 'VERIFIED'
    assert remote.writes == 1 and remote.files == plan.files
    assert (ledger/JOURNAL/'RP-001/A001/events.jsonl').read_bytes() == before


@pytest.mark.parametrize('case', ['missing', 'untracked', 'modified', 'git-symlink', 'oversized', 'non-utf8', 'private-path'])
def test_source_reference_stage_rejects_unsafe_or_nonpublic_inputs(ledger, case):
    head, row = source_reference_fixture(ledger)
    source = ledger/'src/tb4/synthetic.py'
    if case == 'missing': source.unlink()
    elif case == 'modified': source.write_text('synthetic = False\n')
    elif case == 'untracked':
        git_fixture(ledger, 'rm', '--cached', 'src/tb4/synthetic.py')
    elif case == 'git-symlink':
        blob = git_fixture(ledger, 'hash-object', 'src/tb4/synthetic.py')
        git_fixture(ledger, 'update-index', '--cacheinfo', '120000,'+blob+',src/tb4/synthetic.py')
    elif case == 'oversized':
        source.write_text('X'*2_000_001)
        git_fixture(ledger, 'add', 'src/tb4/synthetic.py')
    elif case == 'non-utf8':
        source.write_bytes(b'\xff'*12)
        git_fixture(ledger, 'add', 'src/tb4/synthetic.py')
    elif case == 'private-path':
        history = [json.loads(line) for line in (ledger/JOURNAL/'RP-001/A001/events.jsonl').read_text().splitlines()]
        history[1]['evidence'][0] = history[2]['source_evidence_correction']['old_value'][0] = 'private/secret.py'
        save(ledger, JOURNAL+'/RP-001/A001/events.jsonl', history)
        git_fixture(ledger, 'add', 'docs')
    if case in {'untracked', 'git-symlink', 'oversized', 'non-utf8', 'private-path'}:
        git_fixture(ledger, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                    'commit', '-m', 'synthetic negative source state')
        head = git_fixture(ledger, 'rev-parse', 'HEAD')
    with pytest.raises(LedgerError):
        prepare(ledger, row, 'work/fixture', head, reachable=lambda _: True)


def test_source_reference_change_after_prepare_blocks_serialized_publication(ledger, tmp_path):
    head, row = source_reference_fixture(ledger)
    plan = prepare(ledger, row, 'work/fixture', head, reachable=lambda _: True)
    (ledger/'src/tb4/synthetic.py').write_text('synthetic = False\n')
    remote = Remote()
    remote.head = head
    with pytest.raises(LedgerError, match='SOURCE_REFERENCE_DIRTY'):
        send(ledger, plan, remote, tmp_path/'source-reference-dirty.json')
    assert remote.writes == remote.commits == 0


def prepare(*args, **kwargs):
    return real_prepare(*args, base_verifier=fixture_base, **kwargs)


def validate_plan(*args, **kwargs):
    return real_validate_plan(*args, base_verifier=fixture_base, **kwargs)


def outcome():
    return event(2, "OUTCOME", "RP-001-A001-0001", "PASS")


@pytest.fixture
def plan(ledger):
    return prepare(ledger, outcome(), "work/fixture", SHA, reachable=lambda _: True)


class Remote:
    def __init__(self, *, fail=None):
        self.head = SHA
        self.files = {}
        self.fail = fail
        self.writes = 0
        self.commits = 0

    def read_ref(self, branch):
        if self.fail == "read":
            raise RuntimeError("synthetic private provider canary")
        return self.head

    def create_commit(self, parent, files, message):
        self.commits += 1
        if self.fail == "commit":
            raise RuntimeError("synthetic private provider canary")
        self.files = dict(files)
        return "b" * 40

    def update_ref(self, branch, expected, commit):
        if self.fail == "race":
            self.head = "c" * 40
        if self.fail == "before_write" or self.head != expected:
            raise RuntimeError("synthetic conflict")
        self.head = commit
        self.writes += 1
        if self.fail == "after_write":
            raise RuntimeError("synthetic lost acknowledgement")

    def read_files(self, commit, paths):
        if self.fail == "readback":
            raise RuntimeError("synthetic unreadable remote")
        if self.fail == "corrupt":
            return {}
        return self.files


def send(ledger, plan, remote, pending):
    return publish(plan, remote, pending, validator=lambda p: validate_plan(ledger, p, reachable=lambda _: True))


def test_atomic_outcome_clears_cursor_without_changing_worktree(ledger, plan):
    before = load(ledger, RESUME)
    assert before["unsettled_intents"]
    assert json.loads(plan.files[JOURNAL + "/RP-001/A001/events.jsonl"].splitlines()[-1])["event"] == "OUTCOME"
    assert "unsettled_intents: []" in plan.files[RESUME]
    assert load(ledger, RESUME) == before
    validate_plan(ledger, plan, reachable=lambda _: True)


def test_manifest_evidence_projections_and_cursor_form_one_candidate(ledger, tmp_path):
    accepted = tmp_path / "accepted"
    shutil.copytree(ledger / "docs", accepted / "docs")
    accept(accepted)
    manifest = load(accepted, PLAN + "/manifest.yaml")
    evidence = {p.relative_to(accepted).as_posix(): p.read_text()
                for p in (accepted / PLAN / "evidence").rglob("*.json")}
    plan = prepare(ledger, outcome(), "work/fixture", SHA, manifest=manifest,
                   evidence=evidence, reachable=lambda _: True)
    assert PLAN + "/manifest.yaml" in plan.files
    assert "- [x]" in plan.files[PLAN + "/CHECKLIST.md"]
    assert plan.files[PLAN + "/steps/RP-001.md"].count("[x]") == 4
    validate_plan(ledger, plan, reachable=lambda _: True)


def test_fresh_intent_is_ready_only_after_full_readback(ledger, tmp_path):
    row = event(2)
    row["action_id"] = "SECOND-INDEPENDENT-ACTION"
    plan = prepare(ledger, row, "work/fixture", SHA, reachable=lambda _: True)
    remote = Remote()
    pending = tmp_path / "pending.json"
    receipt = send(ledger, plan, remote, pending)
    assert receipt["next"] == "RECORDED_ACTION_READY" and remote.writes == 1
    # After a cold return, even a successful pre-action receipt permits inspection
    # only: the helper cannot know whether the action already took place.
    assert reconcile(pending, remote)["next"] == "INSPECT_ACTION_EFFECTS"
    assert remote.writes == 1


@pytest.mark.parametrize("stage", ["read", "commit", "before_write", "after_write", "readback", "corrupt", "race"])
def test_faults_preserve_pending_and_never_authorize_action(ledger, plan, tmp_path, stage):
    remote = Remote(fail=stage)
    pending = tmp_path / "pending.json"
    result = send(ledger, plan, remote, pending)
    assert result == {"state": "UNKNOWN", "next": "INSPECT_PUBLICATION_NO_ACTION"}
    assert pending.exists() and "provider canary" not in pending.read_text()
    writes, commits = remote.writes, remote.commits
    remote.fail = None
    inspected = reconcile(pending, remote)
    assert inspected["next"] != "RECORDED_ACTION_READY"
    assert (remote.writes, remote.commits) == (writes, commits)


def test_lost_ack_reconciles_exact_commit_without_duplicate_write(ledger, plan, tmp_path):
    remote = Remote(fail="after_write")
    pending = tmp_path / "pending.json"
    send(ledger, plan, remote, pending)
    remote.fail = None
    assert reconcile(pending, remote)["state"] == "RECONCILED"
    assert remote.writes == remote.commits == 1


def test_remote_conflict_creates_no_commit(ledger, plan, tmp_path):
    remote = Remote()
    remote.head = "c" * 40
    pending = tmp_path / "pending.json"
    assert send(ledger, plan, remote, pending)["state"] == "UNKNOWN"
    assert remote.commits == remote.writes == 0
    assert reconcile(pending, remote)["state"] == "CONFLICT"


def test_reusing_pending_record_refuses_second_mutation(ledger, plan, tmp_path):
    remote = Remote()
    pending = tmp_path / "pending.json"
    send(ledger, plan, remote, pending)
    with pytest.raises(LedgerError, match="PENDING_RECORD_EXISTS"):
        send(ledger, plan, remote, pending)
    assert remote.writes == 1


def test_cold_resume_before_or_after_unknown_execution_is_inspection(ledger):
    # The same public intent is consistent with both interruption points. No
    # hidden assumption that an absent outcome means the workload never ran.
    for execution_may_have_happened in (False, True):
        assert cold_resume(ledger, reachable=lambda _: True)["decision"] == "INSPECT_ACTION_EFFECTS"


def test_serialized_plan_cannot_rewrite_history(ledger, plan):
    altered = copy.deepcopy(plan)
    p = JOURNAL + "/RP-001/A001/events.jsonl"
    rows = altered.files[p].splitlines()
    first = json.loads(rows[0])
    first["expected"] = "Rewritten"
    altered.files[p] = json.dumps(first) + "\n" + rows[1] + "\n"
    with pytest.raises(LedgerError, match="HISTORY_REWRITTEN"):
        validate_plan(ledger, altered, reachable=lambda _: True)


def test_cursor_identity_override_and_secret_fields_rejected(ledger):
    with pytest.raises(LedgerError, match="CURSOR_OVERRIDE_REJECTED"):
        prepare(ledger, outcome(), "work/fixture", SHA, cursor_updates={"source_commit": "b" * 40}, reachable=lambda _: True)
    row = outcome()
    row["observed"] = "gh" + "p_" + "CANARY" * 5
    with pytest.raises(LedgerError, match="PUBLIC_DATA_REJECTED"):
        prepare(ledger, row, "work/fixture", SHA, reachable=lambda _: True)


def test_pending_digest_corruption_blocks_readback(ledger, plan, tmp_path):
    pending = tmp_path / "pending.json"
    remote = Remote()
    send(ledger, plan, remote, pending)
    value = json.loads(pending.read_text())
    value["plan"]["branch"] = "another"
    pending.write_text(json.dumps(value))
    with pytest.raises(LedgerError, match="PENDING_DIGEST_MISMATCH"):
        reconcile(pending, remote)


def test_native_git_transaction_preserves_index_and_dirty_worktree(ledger, tmp_path):
    git_fixture(ledger, "init", "-b", "main")
    git_fixture(ledger, "config", "user.name", "Fixture")
    git_fixture(ledger, "config", "user.email", "fixture@example.invalid")
    git_fixture(ledger, "add", ".")
    git_fixture(ledger, "commit", "-m", "fixture")
    remote_path = tmp_path / "remote.git"
    remote_path.mkdir()
    git_fixture(remote_path, "init", "--bare")
    git_fixture(ledger, "remote", "add", "origin", str(remote_path))
    git_fixture(ledger, "push", "origin", "main")
    head = git_fixture(ledger, "rev-parse", "HEAD")
    plan = prepare(ledger, outcome(), "main", head, reachable=lambda _: True)
    save(ledger, "unrelated.txt", "uncommitted user work\n")
    git_fixture(ledger, "add", "unrelated.txt")
    before_index = git_fixture(ledger, "write-tree")
    receipt = send(ledger, plan, GitBackend(ledger), tmp_path / "pending.json")
    assert receipt["state"] == "VERIFIED"
    assert git_fixture(ledger, "rev-parse", "HEAD") == head
    assert git_fixture(ledger, "write-tree") == before_index
    assert (ledger / "unrelated.txt").read_text() == "uncommitted user work\n"
    assert GitBackend(ledger).read_ref("main") == receipt["commit"]


def test_cli_reports_safe_failure_without_raw_provider_or_paths(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "resume"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "BLOCKED" and str(tmp_path) not in json.dumps(result)


def test_native_checkout_guard_rejects_wrong_parent_and_changed_documents(ledger):
    git_fixture(ledger, "init", "-b", "main")
    git_fixture(ledger, "add", ".")
    git_fixture(ledger, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
    head = git_fixture(ledger, "rev-parse", "HEAD")
    verify_checkout_base(ledger, head)
    with pytest.raises(LedgerError, match="CHECKOUT_BASE_MISMATCH"):
        verify_checkout_base(ledger, "b" * 40)
    path = ledger / RESUME
    original = path.read_text()
    path.write_text(original + "# uncommitted document change\n")
    with pytest.raises(LedgerError, match="DOCUMENT_BASE_DIRTY"):
        verify_checkout_base(ledger, head)
    path.write_text(original)
    save(ledger, "docs/untracked.md", "not part of public base\n")
    with pytest.raises(LedgerError, match="DOCUMENT_BASE_UNTRACKED"):
        verify_checkout_base(ledger, head)
