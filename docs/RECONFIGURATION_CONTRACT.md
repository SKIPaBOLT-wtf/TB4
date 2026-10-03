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

The C2 source adds [A-003](implementation-plan/revisions/R2/amendments/RP-027/A-003-protected-first-run-candidate.md):
closed native candidate metadata, an immutable complete original-profile archive
and a separate same-identity actual Setup. Known operation history, selected
credential metadata and protected network-table selection survive. Old derived
packages stay in the archive and cannot become new routing evidence. Existing
first-run binding freezes remain unchanged. Review uses actual Prerequisites and
CommissionedStorage with fresh environment/credential/access/readback/instruction
checks; persisted readiness and arbitrary READY callbacks cannot activate it.
The desktop staged controller retains default denied activation. Explicit local
recovery promotes only the exact schema/binding/previous-state-checked pending
frame. Original profile bytes, authority and workload records remain unchanged.
This unit keeps role/root/backend/domain/layout/fixed identity unchanged. C3 root
relocation and C4 monotonic publication/cache invalidation/promotion remain required.

The C3 Docs source adds [A-004](implementation-plan/revisions/R2/amendments/RP-027/A-004-existing-docs-root-moves.md):
an exact existing-object plan anchored to the protected resolution image, a native
per-file pending WAL and shared IDENTITY UNKNOWN before one metadata/parents SDK
update. An opaque per-transition witness disambiguates the exact applied move;
closed optional private storage root_transition selects expected metadata and
does not grant authority. Native locking spans final owner/current intent checks
and send. Lost reply/restart/recovery only inspect the same object/operation; before
or conflict never authorizes resend. First-CAS role fallback remains available and
old-owner shared UNKNOWN is preserved. Physical move facts do not activate routing
or replace first-run verification. Folder rename, proven non-dispatch/inherited
settlement, remote commissioning/catalogue rebind and final promotion remain required.
Full-capacity retained/unknown work must fit protected evidence without omission;
metadata is bounded at128KiB and the actual native frame limit remains1MiB.

Rollback is another monotonic same-authority transition, never an epoch/generation
rewind. Any possibly applied provider effect is inspected at its exact original
identity. A checkbox cannot erase unread work or assert remote cancellation.

The disposition extension [A-005](implementation-plan/revisions/R2/amendments/RP-027/A-005-durable-root-disposition.md)
persists PREPARED before effect start and INVOKING with exact
native readback under the same exclusive lock before SDK invocation. A fresh
authorized REVOKED transition from actual PREPARED fences the prior live native
revision; typed current/previous/binding/metadata proof establishes only local
non-dispatch. Legacy absence, possible-send or contradictory after metadata never
counts as unsent. Shared UNKNOWN and activation remain held for later qualified
settlement; role takeover does not wait for that evidence or acknowledgements.

[A-006](implementation-plan/revisions/R2/amendments/RP-027/A-006-cloud-inherited-root-settlement.md)
adds current-role cloud-only exact inherited root-result inspection. Original
blueprint/fixed references and unique new-parent transition metadata can justify
UNKNOWN-to-COMPLETE under a dedicated summary-only current-owner CAS, retaining
original operation owner/epoch/ID. It requires actual fresh role/source/native
checks and protected intent; no old host/WAL/ACK, SDK move, replay or first-run/
routing grant. Partial-plan continuation and final promotion remain required.

[A-007](implementation-plan/revisions/R2/amendments/RP-027/A-007-proven-no-send-settlement.md)
adds exact actual native revocation-based shared NOT_DISPATCHED settlement,
retaining original identity/epoch/owner and protecting settings/commissioning/
catalogue. Same-owner cursor resume sends no SDK; a later newly armed ROOT_RETRY
requires that exact confirmed unsent receipt. Missing old proof leaves UNKNOWN
held without blocking role takeover. BEFORE/INVOKING/legacy/saved proof cannot
grant retry; ordinary START remains unchanged. No routing activation.

[A-008](implementation-plan/revisions/R2/amendments/RP-027/A-008-shared-root-plan.md)
requires a small immutable shared root destination/blueprint/fixed-reference/work
witness before any new SDK move. Native intent precedes its strict CAS; an unknown
plan receipt never arms SDK. Fresh actual current-role partial-root facts read only
the exact original fixed objects under old or shared-target unique after metadata,
with actual existing blockers and public counts. No old host/WAL/ACK or READY/
routing grant; ordinary full first-run verification still rejects partial roots.

[A-009](implementation-plan/revisions/R2/amendments/RP-027/A-009-current-role-partial-plan-adoption.md)
adds actual current-role continuation from fresh zero-blocker ordered partial
facts and exact terminal progress receipt. Its immutable native evidence and
separate closed current-installation WAL preserve the original main/work/fixed
Doc/tab/domain. The concrete resumed controller reuses the existing exclusive
PREPARED/INVOKING/send/inspect/recovery paths for newly prepared BEFORE remainder;
old stores are not inputs, and ambiguous/AFTER operations are never reissued.
Actual current prefix/profile/source/native/role/plan/work checks remain mandatory.
Native evidence and WAL cuts promote only the exact protected frame; first-run,
same-authority rebind and final C4 admission remain separately qualified.
