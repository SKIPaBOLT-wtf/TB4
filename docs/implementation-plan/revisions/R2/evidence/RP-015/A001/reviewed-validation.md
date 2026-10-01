# RP-015 / A001 reviewed native authority transaction

Implementation source: `564207f3094cd7b9a5b16b61d2f82ea1d7bcc332`. Local/full-CI/native test head: `1f44283c27669666874a770a628f2f87cad4fe17`.
Corrected progress head: `300085a5daa3efeb0d483cc1afc5c394d2ff9ff4`. Ownership base: `efb71de8f4bc208c041371ca41ad26d840e830e5`.
PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/23 . All src/tests/tools/protocol/packaging/skill/workflow bytes equal the test head after progress corrections.

## Accepted implementation scope

NativeDocsAuthority constructs actual configured document/tab get and strict requiredRevisionId batchUpdate requests around an injected authorized SDK service. It uses one atomic delete/insert batch, UTF16 ranges, preserves the final newline, validates canonical bounded R2 JSON/domain and rejects extra/malformed/rich/suggested control structure. BMP private-use characters are JSON-escaped because the provider strips them; actual wire budgets are checked. Per-principal opaque revision tokens are neither leadership epochs nor transferable snapshots.

RecordMutation freezes canonical typed before/after/protected records, fixed header/domain and caller-pinned current owner/epoch. A pending forced request fences the old actor. Benign heartbeat/unrelated record changes are preserved under a fresh strict CAS; foreign operation/generation/payload/result or owner changes cannot be overwritten. After any accepted/ambiguous mutation the helper only reads; complete same-operation desired state confirms even if metadata revision advanced. Missing/stale readback remains UNKNOWN and requires INSPECT, never an assumed failed write/replay. Read/write budgets are explicit and finite, not a claim of network wall-time bounds.

terminal_publication validates request binding/INLINE bytes/hash or protected exact ARTIFACT descriptor, result hash/semantics and RETURNING stage; it atomically commits UNREAD result retention and AWAITING_CONSUMPTION status. It never executes a payload, fetches artifact bytes, creates an authority, renames raw control files or manufactures a result. The existing result is preserved. Generic record mutation cannot elect an owner or alter force flags; RP016 supplies those typed transitions.

This is an unreleased internal transport/helper correction, unwired from installed v1. Role authentication, local protected credentials, durable outbox, transport timeout/response-size enforcement before parsing, quotas/backoff, actual commissioning, live migration and end-to-end ordinary publication remain later gates. File ACLs do not implement role-level field permissions; arbitrary unrestricted editors can bypass cooperative checks. Shared-state CAS cannot revoke already-dispatched OS/network effects or require every sink's ACK.

## Check mapping and reviewed assertions

- C1: the RP013 positive benign-metadata invariant now passes in both selected native-adapter wire tests and independent atomic model. A first stale CAS is rejected, fresh same-operation read validates, one actual logical commit finalizes the original result. Legacy raw-file counterexample remains a negative test rather than a qualified fallback; its historical xfail marker is retired only with this passing R2 port. DEF001 remains OPEN for RP047/048/end-to-end scopes.
- C2: actual request bodies and exact tab/document binding inspected. Tests cover changed metadata, delayed/stale receipt visibility, ambiguous apply/lost reply/non-apply, stale owner/force flag, typed field drift, malformed content, and whole atomic batch rejection. R2 eliminates a separate authoritative final rename; failing the batch cannot leave only deleted control or a half-renamed terminal record.
- C3: success, same-operation idempotent read-only confirmation and unresolved conflict/UNKNOWN are distinct. Unknown requests never cause another mutation in that call; explicit INSPECT mode after restart never sends. Concurrent foreign work/result/input descriptor is preserved. No helper interface takes an execution callback, PID, workload replay or discovery/root creation.
- C4:106 new cases run in the shared and wire suites; complete affected regressions and native package tests pass. Exact nodes are retained. Documentation distinguishes the Google atomic primitive from application identity, cooperative role/clock policy and still-required transport/durability/qualification boundaries.

## Validation provenance

Windows Python3.11 with process-local venv PATH, PYTHONUTF8=1 and PYTHONPATH=src. Fresh nonexisting task-owned pytest temp; no shared temp deletion. Exact command targets:
`python -X utf8 -m pytest tests/drive tests/fetcher tests/feasibility tests/protocol tests/development tests/integration/test_cancellation_race_reproduction.py tests/integration/test_result_publication_reproduction.py tests/integration/test_google_transactions.py --basetemp <fresh-task-temp> -ra`.

Observed final local exit0: **1018 passed,2 skipped,4 xfailed in24.45s**. Collection1024 nodes in0.45s, local-collected-nodes.txt. Skips remain the POSIX file-mode assertion/Windows native ACL gate and POSIX SIGTERM-ignore behavior. Four strict expected failures are RP014's two cancellation invariants across two modeled platforms; they are not fixed by storage work. No new test is skipped or expected to fail.

[Linux CI36795042935](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36795042935), job110156441740, test mergece9fcf3b87e8d69e393d1fe0deb56f100ef266de: **1435 passed,2 skipped,4 xfailed in18.85s**. Corrected-progress same-code [CI36795340448](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36795340448), job110157376551, merge8cd3ce9:1435/2skip/4xfail18.66s. [Progress36795340439](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36795340439), job110157376337: schema/ledger, development tests, accepted-history preservation and scanner PASS. Local canonical ownership-base ledger also PASS (14 previously VERIFIED), scanner clean, diff-check/source equality exit0.

[Native Desktop36795042871](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36795042871), same exact test merge:

- Windows job110156441227: GUI63 passed/4 skipped2.14s; WATCHDOG/FETCHER builds and both packaged self-test, GUI smoke, install/uninstall/profile isolation PASS.
- Ubuntu22.04 job110156441470: GUI67 passed2.08s; full suite1445 passed/4 xfailed21.08s; both role builds and all packaged acceptance PASS.

Provider-reported artifact provenance (not downloaded/rehashed): Windows11133093563,119324652 bytes,sha256:68dc61885a84b657269f48d888dfa12a7339ac76ffd8467d67d36248d8360e97; Linux11132628757,312213296 bytes,sha256:9af6ecd69a3e7db3912615cf585b32c606645a37e5c7fac4bf27abdfa7b291bd. No artifact was installed on the user's host or copied into the knowledge archive. The automatic additional same-code run36795340449 is tracked through final review before merge.

## Failures preserved and scoped repair

1. Source8e478f13eafca2b6f049b15b45ba3aa3cd16951d introduced a test basename already used by historical feasibility tests. Local collection failed exit2/one error0.73s; Linux CI36794242375 job110153897268 also failed (2skip/one error1.98s); Desktop36794242426 Linux job110153897721 failed collection, Windows job110153897653 completed successfully. DEF015 records the source and repair. Only the new module was renamed to test_native_docs_transport.py, retaining all assertions and historical tests. Source5ed368e0e18806b091ba435fa5fb259bf2842c94 then passed local995/2skip/4xfail24.14s; CI/Progress and Desktop36794419490 completed. Those earlier builds are not final-source proof.
2. Despite those green tests, a bounded no-write diagnostic changed inline text while retaining the old digest and result; terminal_publication wrongly accepted a plan. DEF016 records the shape-versus-byte-integrity gap. Sourced429b6b4cba42bae2a0aff37399d3eed27748f58 added full request validation and protected artifact descriptor. Local1012/2skip/4xfail24.55s,1018collected; CI/Progress and Desktop36794772240 completed.
3. Further exact-type diagnostic changed protected integer10 to float10.0; Python equality still returned READY, writes0. Final source uses canonical bytes for before/after/protected identity and strict descriptor scalar types. Exact negative concurrency/confirmation tests now reject this; all repair units remain in A001 journal.
4. This session mistakenly indexed those two DEF016 repair units as two copies of attemptA001. Progress36795042924 job110156441158 and typed local ledger rejected REPAIR_ATTEMPT_REUSED. The exact invalid registry record is preserved in invalid-repair-index.json and prior Git commits; append-only intent0021/outcome0022 correct the mutable current index to one real A001 attempt. Both source-repair intents0011/0016, outcomes, hypotheses and failures remain. No validator rule, test or prior accepted record changed. Corrected current/canonical-history Progress passes.

DEF015 and DEF016 can close only with coordinated RP015 VERIFIED and these passing checks. DEF001 and DEF002 remain OPEN; this step does not prove historical initiating cause or deployed repair. Failed source/test receipts are not overwritten.

## Privacy, rollback and limits

All fixtures use synthetic identities/content and fake services; no real Google request was made in this step. Raw provider exceptions are converted to fixed codes without messages. Diff and scanner reviewed; no real topology, host name, credential, private root or runtime trace published. Canonical R2 layout/operation binding retained; installed v1 and historical immutable evidence unchanged.

Rollback removes the unreleased adapter/helper additions. It does not restore stale live authority, lower epochs, clear UNKNOWN work or silently re-enable mixed writers. Actual Docs primitive evidence remains RP008 A001; this step verifies request construction and reconciliation against that documented contract, not provider latency/multi-host behavior. Durable write-intent/recovery and actual runtime publication are mandatory later gates.
