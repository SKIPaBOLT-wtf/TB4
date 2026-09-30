# RP-010 A-001 — append-only STARTED reference correction

DEF-012, detected before RP-010 acceptance. Event RP-010-A001-0006 was published
with its own ID in related_event instead of the already-published INTENT 0005.
The run and action exist; no execution was unauthorized. Its cursor also omitted
the pending intent. Old event bytes must remain unchanged.

Extend the existing CORRECTION event with an optional closed reference_correction
object: field (only related_event), old_value, new_value. This applies only to an
earlier STARTED event. Require exact old value, a different new value, one correction
per target, matching action/check/source/run identity, and an earlier matching
INTENT that was pending at the original STARTED position. Correction is RECORDED
with observed justification. It cannot rewrite INTENT, outcome, evidence, sequence,
timestamp or source, close/reopen pending actions, or manufacture retrospective
authorization. Return original events unchanged; only resolve this administrative
reference during validation. Existing prose-only corrections retain their meaning.

This adds a narrowly scoped administrative recovery capability to RP-001's record
contract; previously accepted records and gates retain their meaning. RP-010
acceptance is held; all existing ledger/history/defect/publication regressions and
new adversarial correction tests must pass. No accepted ledger defect is alleged:
the old validator correctly rejects the malformed publication. Repair ownership
is RP-010, where the clerical error was introduced. Existing RP-001 evidence remains
immutable; no earlier acceptance is based on the malformed RP-010 record.

The session publisher must derive STARTED references from the current INTENT and
preserve every pending intent in the cursor; never hard-code sequence arithmetic.
The supported ledger CLI is python -X utf8 -m tools.development.ledger --base SHA,
without a validate subcommand. The initial invocation failure remains in history.
