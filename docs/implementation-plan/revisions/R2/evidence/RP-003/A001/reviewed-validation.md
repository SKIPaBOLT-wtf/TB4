# RP-003/A001 reviewed defect provenance

Source: `dd24ce579220b60a58fb2bc036b6c3658cc409de`. Exact final CI checkpoint: `7532a740a134c472935ad088fe75afbea8177d9b`. [PR 10](https://github.com/SKIPaBOLT-wtf/TB4/pull/10).

## Observed verification

Windows Python 3.11: `python -m pytest tests/development tests/security tests/desktop/test_plan.py -ra --basetemp .venv/pytest-rp003-a001-r2`: 88 passed in 13.30 s, exit 0. Ledger history against `dd29900bdf946012a5a424d4dcce9f16e14870c2`, public repository scan and diff checks passed.

[CI 36763117414](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36763117414), job 110050432111: 724 passed, 2 optional GUI skips in 11.33 s. [Progress 36763117407](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36763117407) and [36763111946](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36763111946) passed. No installer workflow was required by this development-only source change.

## Check review

C1: closed defect schema separates detected location, suspected and proven origin, reproduction failing/passing SHA and requirement impact. `test_unknown_culprit_is_valid_but_unproven_origin_is_not` rejects absent proof; all declared commits must be reachable. Lossless v1 migration preserves every original field. Source guesses are not promoted into proven origins.

C2: `test_repair_snapshot_and_transitive_hold_preserve_failed_hypotheses` checks a three-step accepted dependency chain, later attempts, retained receipt/build references and failed hypothesis. Candidate creation is pure. Concurrent in-progress work is refused, while never-started dependents remain planned. History checks preserve snapshots, hypotheses, repairs and existing evidence bytes.

C3: issue-closure-only resolution, cleared rechecks, old-build acceptance and incomplete recheck sets are rejected. `test_new_repair_cannot_omit_transitive_rechecks` and `test_serialized_repair_cannot_bypass_impact_review` guard both preparation and serialized publication. Invented legacy exemptions are rejected. New reviewed receipts are required on later attempts; dependencies return in order.

C4: `test_synthetic_intent_outcome_evidence_and_reacceptance_use_checkpoint` runs the RP-002 preparation/publication/readback protocol using an injected synthetic remote, then records fixture-only outcome/evidence and reaccepts three steps in order. No real workload is executed. Existing authenticated connector checkpoint transactions were read back for every changed file. DEF-001/002 retain OPEN, null origins, null passing source and original IP-68 evidence. Issue 7 was inspected as OPEN; no issue or pilot was changed.

## Retained failure and scope

Initial source `065b56939b2761d73f7b12698995f6bb6379ad5f` passed Windows 84 tests and Linux 720 tests (2 optional GUI skips). Source review still found DEF-008: a manually appended repair could omit transitive impact or forge a legacy exemption. Events 0005/0006 preserve that finding and repair intent; final source adds transition-level guards and four negative tests. Acceptance was withheld until those checks passed.

Synthetic fixtures and public development records only. No private topology, credentials, provider dump, installed runtime, workload replay, network changes or live pilot acceptance. Review included invariants, history/privacy, compatibility and rollback. Reverting helper wiring requires corrective history and manual write-ahead records; earlier failures and acceptance holds must remain. C1-C4 can be accepted for development infrastructure, with deployment/pilot gates still pending in later steps.
