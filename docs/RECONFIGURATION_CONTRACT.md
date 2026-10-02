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

The foundation alone does not satisfy any RP-027 check. The controller must still
persist exact maintenance/resolution intent, support bounded resolution of existing
work without replay, stage a candidate through actual first-run checks, retain old
private configuration until new access/readback succeeds, qualify same-authority
root relocation and fallback/crash recovery, then publish a monotonic descriptor/
configuration/leadership transition and invalidate stale local caches/leases.

Rollback is another monotonic same-authority transition, never an epoch/generation
rewind. Any possibly applied provider effect is inspected at its exact original
identity. A checkbox cannot erase unread work or assert remote cancellation.
