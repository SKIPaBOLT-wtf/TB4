# RP-016 A001 reviewed leadership acceptance

Source: dfa260eae0675db46a2c56424cc4b5adbf348400; test head: 4e0eac60ad496e3b2feb78f7eb7c01f701329f56; base: 3924958a9257d8d2f03495481a4040bea6407f30.
PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/24.
Native merge tested: fa7ce51e10b57e933610729ddea307cf9d30b67a.

## Invariant review
C1: Leadership.observe/acquire/renew/confirmed_grant persist a closed owner installation UUID, independent display name, epoch, acquisition/transition ID and heartbeat sequence/time in the one RP-015 native authority. Explicit commissioning is required for an empty layout. Only an actual confirmed same-helper acquisition yields a grant; unrelated fields survive fresh CAS reconciliation.
C2: ElectionMutation compares both authority rows byte-for-byte under strict requiredRevisionId. Generic RP-015 RecordMutation guards owner/epoch and pending request. Resumed old owners cannot renew/write; current_before_dispatch freshly checks the pinned grant and force slot. This is cooperative admission, not atomic revocation of an external effect after the check.
C3: 63 new wire/model cases exercise all six concurrent-claim orders on two backends, old snapshots after renewal, first stale read, partition/rejoin, lost reply/readback, inspect-only restart, unreliable/backward clocks, request expiry/contention, overflow and forged/malformed input. Exact node IDs accompany this review. No real network, device, credentials or OS suspend experiment was performed.
C4: epoch+1 is directly ACTIVE after complete readback. Stale timestamp permits the first successful CAS immediately, with no second grace window and no old-owner/sink ACK. Forced request stores requester identity/name without replacing the incumbent until claim. Unknown old jobs remain unchanged. An explicit suspension counterexample shows a previously admitted external effect can occur after takeover; it is neither erased nor authorized for replay.

## Observed validation
Windows Python3.11: process-local venv PATH, PYTHONUTF8=1, PYTHONPATH=src.
Command: python -X utf8 -m pytest tests/drive tests/fetcher tests/feasibility tests/protocol tests/development tests/integration/test_cancellation_race_reproduction.py tests/integration/test_result_publication_reproduction.py tests/integration/test_google_transactions.py --basetemp <fresh-task-temp> -ra.
1081 passed, 2 skipped, 4 xfailed in 26.38s, exit0; same selection collected 1087 nodes in0.44s.
Two platform skips concern POSIX mode and SIGTERM behavior. Four strict expected failures retain DEF-002/RP-014 cancellation/deadline defects; DEF-001 also remains open for end-to-end publication integration.
CI run36796974836/job110162535382: 1498 passed,2 skipped,4 xfailed in18.14s, success.
Progress run36796974706/job110162534918: success.
Desktop run36796974733: Windows job110162534974 GUI63 passed,4 skipped in3.35s; Ubuntu22.04 job110162535147 GUI67 passed in2.06s and full1508 passed,4 xfailed in20.81s. Both roles' builds, bundle self-tests, GUI smoke and installer/uninstaller profile isolation PASS on both platforms.
Provider-reported artifacts (not independently downloaded hashes): Windows11134256404,119332833B,sha256:1625363f8787d1e57daf318655ff9ec4bac9bab98dc31680f9cc4dd9d8091070; Linux11134426027,312240806B,sha256:eb4b2a8658fdec62fc61eaec2e5f371c61e4b45f6fa627c64a88648ee90b79a5.
Local ownership-base ledger, public privacy scanner and diff whitespace check passed before this evidence publication.

## Scope and rollback
This is tested, unreleased leadership implementation through the real request adapter and an independent atomic model. Provider CAS itself was separately observed in RP-008. Runtime wiring, durable local plans, trusted credential/clock provenance, network deadline/rate enforcement, local instance guard, GUI button and multi-host pilot remain later gates. Installed v1 is not migrated. Rollback removes unwired additions; never rewind a live epoch, clear a valid owner or discard unknown work.
