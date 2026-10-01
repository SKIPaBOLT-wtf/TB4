# Available native WATCHDOG leadership (RP-016, unreleased)

`tb4.drive.leadership` prepares typed ownership/force-request transitions and
commits through RP-015's exact native document CAS/readback. It has no host/sink,
process, network, credential or GUI side effect. RP-017 integrates coordinator
startup/demotion; RP-053 supplies the actual GUI button. This primitive does not
migrate an installed v1 deployment or grant a device action.

## Persisted records and authority

The bounded global.leadership envelope has generation=epoch, operation_id equal
to acquisition_id, BUSY retention, and a closed body: owner installation UUID,
computer_name, epoch, ACTIVE phase, heartbeat_at (trusted UTC or null),
heartbeat_sequence, acquisition_id and last transition_id. SHA256-shaped IDs are
opaque caller-generated unique operation identifiers, not credential material.
The caller must durably save an intent/plan before sending; epoch/owner and its
identity remain persisted in the one authoritative document across client restarts.

The fixed global.force_request slot is FREE with current epoch, or BUSY with
request_id, requester installation UUID/computer_name, expected_epoch,
requested_at and expires_at. Its envelope binds the same request/epoch. The TTL
is the commissioned lease_stale_s (draft default120s), so a crashed requester
cannot leave an unbounded flag. A trusted clock is required to create/expire that
timestamp-based request; ordinary stale takeover still has the monotonic fallback.

Enrollment maps each unique installation UUID to a private display name. The
same display name may belong to two installations; it never confers ownership.
Enrollment is supplied by trusted commissioning, not obtained by copying another
host's token/profile or trusting the public display string. All public tests use
synthetic names. Files/Docs ACLs still cannot enforce these field-level roles.

## Acquisition and renewal

Only a genuinely empty, generation0 layout admits explicitly commissioned first
ownership. Normal startup cannot recreate/clear an authority or assume ownership
from its own name appearing in a fresh record. It prepares a unique transition
only after the incumbent timestamp is stale under the commissioned profile, or
after qualified local monotonic observations prove the exact owner/epoch and
heartbeat sequence/time unchanged for lease_stale_s. Unrelated summary/work
writes do not count as incumbent heartbeat. Renewed progress resets that proof.
Backward/untrusted wall time never invents a fresh timestamp; a qualified bounded
monotonic window still permits takeover without contacting the old machine.

Claim atomically persists epoch+1, the candidate identity/name and ACTIVE, clearing
the old request slot. There is no ACTIVATING/drain/all-sink acknowledgement phase.
The first strict CAS wins; competing old observations cannot overwrite it.
Unknown/unreachable old jobs remain byte-for-byte in their existing records.
Heartbeat renewal requires the exact pinned owner/epoch/acquisition grant, checks
the force slot and increments its sequence. Epoch/sequence overflow fails closed
instead of wrapping or restoring an earlier authority.

## Forced takeover and uncertainty

An explicit local user request on an enrolled standby prepares the flag. The
incumbent name stays in the owner record while the requester name appears in the
request record. A pending flag stops old shared writes/renewal and the cooperative
dispatch check. The matching requester may immediately conditionally claim the
fresh role, without incumbent acknowledgement, shutdown or sink response.
Another requester cannot overwrite an existing flag. Expiry clear is itself a
conditional transition; an ordinary stale claim can win and clear a pending flag.
An old request cannot transfer a later epoch.

Every transition preserves unrelated records from its fresh snapshot. A CAS
rejection is followed by bounded fresh inspection/revalidation. After an accepted
or ambiguous reply there are only bounded reads, never another mutation. Complete
record equality confirms the same transition. UNKNOWN remains inspect-only;
restart uses the same saved plan and INSPECT mode. Ownership grants are returned
only for this helper's actual confirmed acquisition result, never a manufactured
success object or a result from another actor. Later runtime work must provide
durable local plan storage and authenticated installation/clock provenance.

Before an external dispatch, current_before_dispatch reads the authority and
checks the pinned grant and absence of a flag. It is a cooperative point-in-time
check, not an OS/network lock or bearer credential. A process can suspend after
True, a new owner can win, then an already-admitted effect can occur. The tests
preserve that limitation explicitly. Fresh shared writes remain atomically fenced;
old work is not replayed/cancelled merely because leadership changed. Staleness
makes other candidates eligible; it does not erase the incumbent record itself.

## Proof and remaining integration

Conformance uses the actual native Docs request adapter with synthetic service
responses and an independent atomic model. Cases cover concurrent starts,
powered-off owner/unreachable job, first stale read, renewal versus old snapshots,
partition/rejoin, lost replies/restart, uncertain/backward clocks, force flag
contention/expiry, duplicate computer names, closed record schemas and numeric
bounds. Source-linked reviewed evidence records actual results after execution.

No provider quota, transport latency, real OS clock/suspend behavior, native
credential isolation, local single-instance guard, running WATCHDOG integration
or GUI completion is claimed by these tests. Calls use RP-015's bounded budgets;
runtime scheduling must enforce RP-011 rate reserves and transport deadlines.
The strict CAS provider primitive was separately observed in RP-008. Real
multi-host/pilot acceptance remains later explicit scope. Rollback removes this
unreleased helper; never rewind a live epoch, clear another owner or discard
UNKNOWN work during deployment rollback.
