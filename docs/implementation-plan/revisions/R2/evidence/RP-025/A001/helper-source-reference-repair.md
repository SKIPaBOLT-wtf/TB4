# RP-025/A001 — complete public source-reference staging repair

INTENT `RP-025-A001-0064`; public source `276ce3a035b66c08cab20976dde911cfc3e5f506`; DEF-047; [A-002 administrative amendment](../../../amendments/RP-025/A-002-source-aware-checkpoint-staging.md).

Prospective prepare and serialized-plan validation now retain the exact original historical source references by staging public regular Git blobs from verified expected-head. Current public paths must match those blobs (portable line endings); untracked, missing, changed, symlink, unsupported non-UTF8, private/outside and oversized inputs refuse. Total source input is bounded to2MB. Source bytes are neither imported nor executed. Plans remain docs-only; native product/runtime files and existing ledger/history/receipt/ref gates are unchanged.

Tests preserve exact legacy source_evidence_correction history through prepare/validate/readback and refuse unsafe/post-prepare source changes before writes. Existing tests and all historical evidence remain. Review/whitespace passed; actual test results pending. This admin scheduling consumes only verified RP001-003 and leaves native21-24/A002 and25/A001 holds intact. No live credentials/system/network changes.
