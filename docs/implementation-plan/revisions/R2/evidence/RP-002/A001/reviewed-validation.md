# RP-002/A001 reviewed publication acceptance

Source: `25539e6b0cda63aeb8db544710602fbaa9ca98ca`. CI checkpoint: `fd0e03f92d1d54c3018f6b396cd62ee872b1c110`. PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/9 . Reviewed 2026-09-30T18:43:52Z.

## Exact observed procedures

- Windows Python 3.11: `python -m pytest tests/development tests/security tests/desktop/test_plan.py -ra --basetemp .venv/pytest-rp002-guarded`: **72 passed in 7.31 s; exit 0**.
- `python -m tools.development.ledger --base 9ae6ead9b97fde220c325b63a3c913296e346894`, public repository scan and diff check: exit 0; complete current R2 validated with RP-001 acceptance preserved.
- [CI 36760355814](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36760355814): full minimal-environment Linux suite passed. The optional GUI skips remain outside this development-helper scope.
- [Progress 36760355787](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36760355787) and [36760349139](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36760349139): development regressions, real plan/history and public scan passed. No installer workflow was triggered for this development-only PR.
- Actual guarded CLI preparation succeeded (exit 0, digest `c97ba85d3a1501ee2c42730efe30c3ec97ba72ff16badf462d99aa2cddc0f4ea`) from the exact clean published parent. Its two-file journal/cursor transaction was published as [3036b1e](https://github.com/SKIPaBOLT-wtf/TB4/commit/3036b1ecb6dd44eb8149590234f0cda7f9738e46) through the authorized connector. The candidate SHA was preserved before non-force ref update; **every changed file and final branch ref were read back**, not inferred from an upload response.

## Check mapping and negative review

C1: `test_fresh_intent_is_ready_only_after_full_readback` verifies the new-action boundary; real CLI/connector publication verifies the manual-equivalent route. Prepare/publish bind to the declared clean document base.

C2: `test_manifest_evidence_projections_and_cursor_form_one_candidate` validates four check receipts, manifest, definitions, index and cursor together. The native Git transaction uses one tree/commit and preserves both a dirty worktree and a staged unrelated file. `test_serialized_plan_cannot_rewrite_history` and the stale-base regression prevent loss of existing history.

C3: interruption tests cover no publication, commit creation, failure before ref update, lost acknowledgement after update, readback outage/corruption and a concurrent ref change. `test_cold_resume_before_or_after_unknown_execution_is_inspection` treats both execution possibilities identically: inspect effects; never replay.

C4: `test_faults_preserve_pending_and_never_authorize_action`, `test_remote_conflict_creates_no_commit`, `test_lost_ack_reconciles_exact_commit_without_duplicate_write` and `test_reusing_pending_record_refuses_second_mutation` establish fail-closed continuation and retained safe pending metadata. Provider canary text is never exported. Tampered pending digests and cursor identity overrides fail.

The initial source's review gap is preserved as DEF-007 and events 0006-0008. It was corrected before acceptance: exact HEAD, tracked document cleanliness and untracked document checks run at preparation and publication. No stale-base overwrite occurred during the actual performed transactions.

## Scope, privacy and rollback

This is development infrastructure; no runtime, installed SKILL, live network, credential or deployment mutation. Windows and Linux synthetic/native Git mechanics are qualified. Local GitHub credentials are absent, so authenticated direct GitHub push is not claimed; actual remote publication used the explicitly documented equivalent connector contract. The adapter's native Git mechanics are tested against an isolated bare Git fixture.

Review compared tests with their stated invariants and inspected the candidate/source diff. Only reviewed public source SHAs, branch/check IDs and synthetic data are exported. No raw provider errors or private host/path values are in evidence. Rollback disables this helper and restores mandatory manual publication while retaining every journal/evidence/pending record; no runtime effects require reversal.

Journal: source 0001/0002; tests 0003/0004; PR review 0005/0006; base guard 0007/0008; final verification 0009/0010/0011. Later merge/acceptance events remain separate.
