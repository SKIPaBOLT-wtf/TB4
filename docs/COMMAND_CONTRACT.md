# R2 command, status and ownership contract

RP-010/A001. **UNRELEASED**; installed protocol v1 and its filenames remain
authoritative for installed software. This specification is a handoff, not a
transport adapter, authorization service, process supervisor or migration.

Machine schemas, legal actor/from-stage matrix and synthetic fixtures:
`protocol/drafts/r2-command-contract.json` and `r2-command-fixtures.json`.
`src/tb4/command_contract.py` is the executable specification. Its atomic model
is an explicit hypothesis for later adapter qualification, not evidence that a
Python object comparison is a distributed lock.

## Correlation and bounded identity

Every semantic request, result, status, cancellation and consumption ACK binds
domain UUID, enrolled target UUID, target generation, operation ID, payload SHA256,
and exact protocol 2.0. Computer display names never identify commands. The helper
derives the operation ID as SHA256 of canonical UTF-8 JSON
`["TB4-R2-OP", domain_id, target_id, generation]`. Canonical JSON uses sorted keys,
compact separators, unescaped Unicode and finite values. Generation starts at 1,
never rewinds or wraps, and exhaustion requires an explicit reviewed migration.
Hashes establish correlation/integrity, not sender authorization.

The authority transaction reserves one unconsumed generation per target and
persists its request fingerprint with the target high-water generation. A repeated
identical request returns its existing receipt/status even after its claim deadline.
The same ID with changed payload, interpreter, timing or any other request field is
an identity conflict. A newer generation is BUSY until the old result is consumed;
a gap is rejected. Compact retained history returns an existing receipt after
recycle. Once that history is evicted, the preserved high-water mark rejects old
generations as stale, never executes them again. Registry enrollment, recovery,
backup restoration and generation retention must preserve this invariant.

AdmissionModel is a serial model of that single authority transaction. Its saved
image models already validated, trusted durable state; loading untrusted/corrupt
storage and distributed CAS implementation are later gates. It is not safe to
commit its independent Python mutations piecemeal in production.

## AUTO-SNIFF and common ingress

Read only a configured ingress slot in the pinned authority document. Validate
the exact revision and envelope, closed schema/version, domain/target enrollment,
derived operation identity, finite times, claim deadline, interpreter and payload
integrity before reserving work. Reject duplicate JSON keys, invalid UTF-8, nonfinite
numbers, unknown fields, oversized values and unknown targets. No raw rejected
content is reflected in diagnostics. Rejection receipts bind ingress index,
generation, opaque read revision and SHA256 of the exact submitted bytes even
when the operation ID is missing or invalid. Writing a rejection must condition
on that same ingress revision; a late rejection must not replace its next occupant.

Inline payloads contain at most 256 UTF-8 bytes. Larger/expansion-heavy payloads
use the pre-existing target input artifact slot, with exact generation, byte count
and SHA256 from a trusted complete descriptor verified against downloaded bytes.
The descriptor must come from the target's configured slot binding; an arbitrary
client-supplied descriptor is not evidence. Never execute partial/mismatched media.
Artifact publication and its reference commit require their own later transaction
implementation. Each admitted target is independent; lack of capacity returns a
bounded reason without consuming the next target generation. Cancel/ACK retain
their RP-009 reserved slots during work saturation.

## Orthogonal facts and legal writers

The full status is a projection from **one atomic document snapshot**, exposing
operation binding, receipt, execution, publication, consumption, current stage,
responsible role, stage time, last progress, wait reason, next check, deadline,
terminal flag and result digest. These are different facts:

| Fact | Evidence required |
| --- | --- |
| ADMITTED | Valid request and per-target reservation committed together |
| CLAIMED | FETCHER won the unclaimed generation CAS |
| RUNNING | Durable local execution identity exists; later supervisor must prove it |
| EXITED / INTERRUPTED | Execution report, not heartbeat loss or cancel receipt |
| NOT_EXECUTED | WATCHDOG won unclaimed expiry/withdrawal before any claim |
| Publication CONFIRMED | Exact generation/binding/digest read back from authority |
| Terminal | A report is published and awaiting explicit consumption |
| ACKNOWLEDGED | COACH ACK binds this exact result digest and full operation |
| READY after recycle | ACK and publication confirmed; compact history preserved |

The model writer matrix names **logical roles**, not authentication. Each future
real write must additionally pass current owner/request checks and strict CAS.
RP-008 A-002 applies: stale-owner takeover becomes ACTIVE immediately on winning
CAS without sink acknowledgements; unknown old work is retained individually.
A role takeover never silently relabels an old command as new or retries it.

COACH submits common ingress, cancellation and result ACK. WATCHDOG validates and
routes work, updates host/FETCHER waits, handles unclaimed expiry/withdrawal and
recycles after ACK. FETCHER claims, supervises execution, reports and confirms its
publication. `publish_expiry` is the WATCHDOG nonexecution publication edge for
both claim expiry and preclaim withdrawal. All compare and write the same observed
authority revision; a stale snapshot loses without overwriting the winner.

## Deadlines, cancellation and ambiguity

Timestamps are integer UTC seconds supplied by a validated time policy. Backward
model updates fail without mutation. The future clock policy must qualify skew;
the model does not prove real machine synchronization. A claim is allowed strictly
before claim_deadline. At equality only unclaimed expiry is eligible. Claim and
expiry compete on the same revision; after a successful claim, even a long timeout
can only report UNKNOWN/wait for evidence, never assert NOT_EXECUTED. Starting work
sets an execution deadline independently of the admission deadline. Expiry of the
execution deadline prompts supervision/reconciliation, not a fabricated result.

A cancellation request has its own stable ID and requested time, immutable on
acknowledgement. REQUESTED -> ACKNOWLEDGED -> SIGNALLED records progress only.
UNKNOWN preserves ambiguity; ALREADY_FINISHED requires a known completed execution.
None of these proves interruption. If cancellation won before claim, FETCHER cannot
claim and WATCHDOG may atomically withdraw that unclaimed request with a proven
NOT_EXECUTED result. If claim won first, cancellation applies to that exact local
execution; a natural exit may still produce DONE. Report CANCELLED/PARTIAL only
with actual interruption evidence. Signal/process-tree handling is a later gate.

For normal exit, exit 0 maps to DONE; nonzero with known meaningful effects maps to
PARTIAL, otherwise FAILED with its explicit effects classification. All outcomes
retain the effects field; FAILED is never implicit retry authorization. An unknown
execution remains WAITING_RESULT, with a visible next check and no invented deadline
or terminal success. It retains its reservation and artifacts pending reconciliation.
This does not prevent other target operations or WATCHDOG role takeover.

Publication failure keeps RETURNING even if the local report says DONE. A stale
or different readback digest cannot confirm publication. Reading status/result does
not ACK. Only exact-result ACK permits recycling; unknown work cannot use that edge.
Lost mutation replies require inspection of the same transition and current snapshot,
not a new operation ID. Explicit later effect-review/recovery policies may resolve
unknown work but must not silently weaken these invariants.

## Fixed-layout encoding and output bounds

RP-009 budgets are unchanged. Ingress/work put operation_id and generation in the
record envelope, with remaining request fields in its body. Result/cancel/ACK leaves
omit the redundant full binding: reconstruct it from the validated work and target
registry **in the same authority revision**, and require the leaf envelope's exact
operation/generation. Never combine separately fetched old and new generations.
The result digest covers the reconstructed full binding and report, including any
output artifact descriptor (slot, generation, byte count, SHA256).

The compact status leaf stores stage, responsible role, times, wait reason,
next-check and deadline. Other axes/digest derive from work/result/ACK in the same
document; the larger full status projection is not duplicated into the 512-byte
leaf. Codecs measure the complete serialized entry including JSON key and envelope.
Even schema-shaped values can exceed byte limits due to Unicode/escaping; fail
TOO_LARGE and use a bounded artifact reference. Never truncate a payload, identity,
integrity digest or evidence silently. Tails are deliberately bounded summaries;
full output stays in the pre-existing bounded output artifact. Publication must
verify its bytes before treating the descriptor as complete.

## Vocabulary, compatibility and acceptance limit

FETCH_BALL remains the work/result channel concept. Legacy LOADING/TOSS/CHEW map
to preparation/QUEUED/CLAIMED-or-EXECUTING; RETURNING retains its publication meaning.
Legacy terminal labels remain result outcomes rather than evidence from a filename.
GONE maps to UNKNOWN/WAITING_RESULT pending explicit effect review. RECYCLING/READY
remain consumption/reuse concepts, but WATCHDOG performs the new draft recycle after
COACH's exact ACK. STOP_BALL remains exact-operation cancellation; ACK of that request
is separate from result consumption. WAKE_BONE remains WATCHDOG host/bootstrap work;
DOG_PULSE remains liveness evidence, not successful execution. WATCHDOG keeps its
coordination role. These reviewed mappings propose future vocabulary only. No v1
state machine, schema, file content or installed SKILL is changed by this draft.

Tests qualify schemas, synthetic transition races, integrity, bounded codecs and
restart-image duplicate handling. Production durability, native Docs adapter,
identity/epoch enforcement, artifact transfer, real process cancellation, GUI,
helper wiring, operating-system coverage and end-to-end release remain later steps.
