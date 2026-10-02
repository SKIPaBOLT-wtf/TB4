# Unreleased staged configuration changes

RP-027 changes the configuration of one existing installation and one existing
authority. It does not reset work, migrate between backends/domains, provision a
router, deploy a build or authorize any live operation. Its active amendment is
[R2 RP-027 A-001](implementation-plan/revisions/R2/amendments/RP-027/A-001-staged-same-authority.md).

## Same-authority boundary

The native Docs document/tab/domain, or qualified folder authority identity,
remains the sole ordering point. A storage-root change must relocate/rebind the
same existing fixed objects with actual metadata/access/readback verification.
It must not create another authority. Backend/domain/layout/installation
replacement belongs to separately authorized migration/reset work.

WATCHDOG leadership acquisition and renewal continue during maintenance. A stale
entry permits the first successful strict-CAS contender to take the role; no
incumbent, unreachable computer or all-sink acknowledgement is required. Computer
names are display labels. Maintenance gates new work and identity changes, not
role availability. Already sent external work is not declared stopped by a marker.

## Optional configuration marker

The unchanged global.settings slot can carry a closed configuration-v1 marker:
schema_version 1, positive monotonic configuration revision, ACTIVE or MAINTENANCE
phase, and an exact transition digest. It is configuration data, not a new dog
state or grant. Descriptor generation/registry/catalogue coherence still applies;
the independent configuration revision never replaces a workload generation.

An absent marker preserves the accepted legacy unreleased contract. A present
ACTIVE marker requires fresh matching local configuration admission before normal
dispatch. Normal record plans protect the exact settings row. Maintenance or a
configuration change arriving after plan preparation prevents the normal CAS from
crossing that boundary. Ordinary BALLPARK publication cannot erase a marker or
bypass the separate configuration transaction.

## Inspection and evidence

Inspect one canonical authority snapshot plus schema-validated local setup and
runtime write-ahead state, bound to this installation's current authority. BUSY,
UNREAD and UNKNOWN workload records, local pending mutations and unknown external
effects require exact-operation resolution. Metadata retention and optional
UNKNOWN stable-IP observations do not establish unresolved execution.

The protected evidence helper writes each authority image once to a freshly
selected native private store. It retains canonical bytes, exact private binding,
revision and inspection facts. A first-revision base64 image fits the existing
private frame budget without duplicating a large prior payload. Owner permission,
native directory binding/protection, exclusive lock and exact readback are
required. An interrupted staging file remains inspect-only; the helper never
overwrites or automatically promotes it. UI/export summaries contain only closed
counts and no identities, hashes, paths, addresses, credential material or payloads.

## Required subsequent workflow

The foundation alone does not satisfy any RP-027 check. Complete acceptance still
requires qualified maintenance/resolution transitions and preserved unresolved
work, a candidate through actual first-run checks, retained old private settings
until new access/readback succeeds, same-authority root relocation and fallback/
crash recovery, then a monotonic descriptor/configuration/leadership transition
and stale local cache/lease refusal.

The C1 controller source adds settings-only maintenance entry/adoption, durable
protected local WAL, exact read-only unknown-write inspection and fresh explicit
zero-blocker resolution. Original setup remains unchanged. A resolution binds
configuration/operation, workload bytes, local profile/revision and current owner
epoch; routine heartbeat progress does not invalidate unchanged work. Pending
local writes can only promote their exact binding/schema-checked candidate with
explicit owner approval, and provider recovery remains inspect-only.

Adoption gives the current role holder a local maintenance checkpoint without
claiming access to the previous installation's missing local evidence. It cannot
resolve routing eligibility from its own empty journal. The source guard extension
is [A-002](implementation-plan/revisions/R2/amendments/RP-027/A-002-shared-effect-evidence.md):
the existing global.summary slot retains a closed bounded effects journal, UNKNOWN
before invocation, and the original local unresolved-status maintenance barrier.
Normal publication preserves the whole guarded summary row, including its prior
non-effect data. Bootstrap refuses an occupied unresolved summary rather than
resetting it; guard-aware summary evolution requires its own later qualified helper.
Exact protected native checkpoint CAS
and a durable local reservation fence new work before maintenance inspection;
late replies preserve the reservation. Native/provider pending recovery is always
the same candidate/operation and provider inspection never resends.

Covered fresh zero-blocker shared evidence permits explicit fallback resolution
without contacting the original installation. An unresolved original local barrier
or shared UNKNOWN remains a refusal. Only the original guarded owner can refresh
its local-clear evidence from actual freshly inspected local state; this does not
erase shared UNKNOWN. Bootstrap coverage requires the initial epoch-one owner and
exact protected checkpoint. A later empty owner cannot claim unobserved legacy
effects were resolved. This is a routing-evidence migration limit and never an
all-peer role-election gate. Native checkpoint/effect schemas are pinned only in
UNRELEASED; installed profiles are unchanged. Full guard qualification and the
candidate/root/promotion flow remain required.
Full-capacity retained/unknown work must fit protected evidence without omission;
metadata is bounded at128KiB and the actual native frame limit remains1MiB.

Rollback is another monotonic same-authority transition, never an epoch/generation
rewind. Any possibly applied provider effect is inspected at its exact original
identity. A checkbox cannot erase unread work or assert remote cancellation.
