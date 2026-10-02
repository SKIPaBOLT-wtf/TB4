# RP-025 A-001 — explicit reconciliation of unaccepted dependent work

DEF-046 requires accepted RP-021 and its accepted dependents to reopen while
RP-025/A001 is still unaccepted. The original repair helper correctly rejects
concurrent active work. This administrative extension preserves that default.
It grants no live operation, migration, product change or accepted scope waiver.

An optional closed `reconciled_unaccepted` repair mapping records exactly the
affected active never-accepted dependents: attempt, suspension INTENT/OUTCOME IDs
and a complete public `frozen_step` snapshot. The snapshot must equal the actual
candidate's previous step, have no accepted checks/receipts/history, and retain
its attempt, WIP evidence/amendments and full check holds. Only transitive
dependents of the accepted repair owner are eligible. Planned work stays planned;
accepted work gets the ordinary new attempt and accepted-build snapshot.

Each freeze needs action `SUSPEND-UNACCEPTED-FOR-PREREQUISITE-REPAIR`, a matching
prior INTENT and RECORDED OUTCOME, exact item/attempt/source/check/action identity,
chronology before reopening, and no unsettled action in that journal at freeze.
UNKNOWN/BLOCKED do not settle a possible mutation. Proof is checked at the freeze
so later properly resumed work does not invalidate immutable history.

Reconciliation sets only the never-accepted dependent's status to BLOCKED;
it neither increments its attempt nor invents accepted history. Complete actual
check definitions and transitive impact remain mandatory. History validation may
use the explicit never-accepted snapshot when its base predates that work's first
start; stable definitions/dependencies and prior WIP references must be preserved.
An accepted base cannot be recast as never accepted. Existing repair/hypothesis
prefixes, journals, acceptance snapshots and reviewed evidence remain immutable.

Adversarial candidate, suspension, history and checkpoint/publication tests,
existing default-concurrency tests and ordinary reacceptance must pass before
this extension is used on the actual RP-021 reopening. This repairs navigation
and provenance; the native held-source defect remains open until its separate
new-attempt patch and Linux/Windows/dependent qualification pass.
