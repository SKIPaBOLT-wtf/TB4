# RP-001/A001 reviewed validation

Reviewed 2026-09-30T18:21:05Z. Final source `88f7850895a7f5ed664818538b5c9308cb7aac8f`; CI test checkpoint `d1edecc805cbed348e6a865e9d12fc517bb67786`. PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/8 .

## Observed verification

- Windows Python 3.11, isolated environment: `python -m pytest tests/development tests/security tests/desktop/test_plan.py -ra --basetemp .venv/pytest-rp001-reviewed`: **52 passed in 2.58 s, exit 0**, source `9f475a743e8b712694a00d7bce66116cecf7dd99`.
- Final source has identical tools, tests, product, protocol, config and packaging trees to that Windows-tested source (Git path-limited diff empty). Only the CI test invocation and development records changed afterward.
- [General CI 36757039191](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36757039191): **688 passed, 2 skipped**, exit 0. Skips are the two optional PySide6 GUI modules in the minimal environment.
- [Desktop 36757039221](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36757039221): Linux and Windows jobs passed, including GUI tests, both role builds and packaged/installer acceptance. Full GUI-enabled Linux regression suite passed separately.
- Progress [36757039378](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36757039378) and [36757034135](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36757034135): ledger tests, full R2 validation, append-only history and public scan passed.
- Local `python -m tools.development.ledger --base bf18f8fee79655f949fa4ae41617368c80d3dc0d`, `python tools/scan_public_repo.py` and `git diff --check`: exit 0. Full plan: 64 steps, original 256 checks; no fabricated legacy acceptance.

## Invariant review

C1: closed versioned schemas reject unknown fields; IDs/attempts/phase/timestamp ordering and safe references are enforced. Public metadata allowlists and canary scanning complement mandatory prose review.

C2: `test_bad_evidence_never_verifies`, `test_missing_receipt_rejected`, `test_unaccepted_dependency_rejected`, `test_cursor_disagreement`, `test_cursor_active_attempt_must_match`, `test_event_check_must_exist_in_definition` and projection cases reject unsupported acceptance. A reviewed complete synthetic receipt is accepted.

C3: duplicate/out-of-order events, orphan/duplicate outcomes, UNKNOWN reconciliation, correction preservation, nonexistent/unpublished Git commits and rewritten history are covered by named tests in `tests/development/test_ledger.py`. No mutation is replayed by validation.

C4: complete real plan and lightweight Progress CI verified. A documentation-only work-branch push at b42e04a triggered only Progress (36755836652); installer path selection excludes ordinary progress commits. The initial PR intentionally tested changed workflow wiring and therefore ran installer CI. Documentation checkpoints inside that PR used skip-ci to avoid repeated cumulative PR builds; final main documentation pushes use the lightweight gate.

## Failures retained, scope and rollback

The initial Windows pytest cleanup failure and the initial console-pytest CI import failure remain in the journal/report. Dedicated temporary storage resolved the former; a one-line module invocation corrected the latter. No cleanup of unrelated temporary files occurred.

Source/diff review: all changes concern development enforcement, tests, CI selection and traceable progress. Runtime/protocol/installers/legacy IP acceptance unchanged. Public artifacts reviewed for credentials and real topology; only synthetic fixtures and public provenance retained. Validator diagnostics use safe codes. General prose still requires publication review; regexes do not prove arbitrary prose safe.

Rollback is a corrective Git revert of development tools/CI wiring; keep all journal and prior evidence and return to mandatory manual enforcement. No live effects or irreversible runtime rollback are involved. No deployed-system, alternate-platform or new R2 runtime feature acceptance is claimed.

Journal: implementation 0001/0002; failed test 0003/0004; isolated retest 0005/0006; review repair 0007/0008; CI 0009/0011/0016; invocation repair 0012/0013; final test 0014/0017.
