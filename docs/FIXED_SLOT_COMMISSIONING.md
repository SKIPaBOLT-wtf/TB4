# Explicit fixed-slot commissioning (RP-019)

This unreleased provisioner creates the finite RP-009 layout once in an explicitly
selected empty root. It does not select or migrate an installed profile. The
native Docs authority remains the default design; the optional Linux folder
mode implements the same layout and owner rules.

## Inputs and trust boundary

A protected setup selection supplies root/domain/setup identities, one bootstrap
installation UUID, mode, finite capacity and qualified role/LLM access to that
same exchange. Computer names are display values, not ownership identities.
Credentials, paths and endpoint bindings never enter public artifacts.

The caller holds SetupJournal in a dedicated existing protected local directory.
Its injected protection verifier must qualify OS ACLs and the directory identity;
the journal implements exclusive process locking, bounded canonical checkpoints,
atomic replacement, checksums and readback. A synthetic always-true verifier is
test-only. OS protection, enrollment and credential resolution are subsequent
RP-020/021 gates. A checksum detects corruption, not a hostile trusted user.

Native Drive/Docs clients must enforce qualified authentication, timeout and wire
size limits and disable transport mutation retries. This adapter sets SDK retries
to zero and bounds decoded responses; that is not an early network byte limit.
The optional folder port runs on the already qualified Linux ext4/xfs server
under the accepted RP-018 private-root and fixed-file identity contract.

## One authority before ordinary elections

Before shared authority exists, only the explicitly chosen bootstrap installation
may create it, holding its local exclusive setup lock. This is an initial setup
restriction, never an all-host acknowledgement condition for WATCHDOG takeover.
A copied installation/journal or independent second bootstrap grant is unsupported.

Bootstrap saves seed bytes and UNKNOWN before its one creation call. Google Docs
cannot use a generated raw-file ID, so initial reconciliation uses an exact
domain/setup/slot/operation properties marker within the chosen root. Bounded
initial listing rejects foreign entries, pagination, duplicate slots and missing
authority with artifacts. After pinning, reads use the exact document/tab identity.

The blank document is seeded with strict requiredRevisionId. Folder creation uses
exclusive files, operation xattrs and SQLite initialization; initial seed uses
the same strict RP-018 revision transaction. Receipts alone never prove a seed.
Readback confirms the canonical blueprint before AUTHORITY_READY. This marker
does not mean deployment, descriptor or work execution is ready.

The seed contains the initial RP-016 acquisition. initial_grant recovers it only
after fresh shared owner/acquisition verification. It cannot revive a superseded
owner. Once that authority exists, ordinary stale/forced takeover applies
immediately, with no execution-sink acknowledgement barrier. An unavailable initial
creator after a confirmed seed does not prevent a successor from taking over.

## Bounded resumable allocation

Commissioner takes a current RP-016 grant and its installation's journal section.
Each advance is bounded; the caller supplies renewal, fresh clocks and pacing.
It reserves a raw object ID without creating an object, saves its exact CAS plan
privately, then records the allocation as shared UNKNOWN before dispatching one
create. Only the same live call that confirms a new intent can send that create.

Native raw files use generated IDs. Folder artifacts use fixed opaque names,
exclusive creation, xattr markers and inode identity seals. Each target has two
8 MiB slots. The shared authority preallocates ingress, control, target,
descriptor, bounded history and quarantine records at the selected capacity.

After a restart, pending authority writes are inspected through RP-015. Shared
UNKNOWN allocations are inspected by exact ID and operation, including by a new
owner. Missing objects or lost replies never permit blind recreate. Uncertain
initial folder schema creation is preserved, not reset. Definite later evidence
or separately authorized repair may be required if a create never applied.

A final single current-owner CAS publishes every exact artifact ID/seal in the
target catalogue, marks storage ready and frees only the initial never-used
artifact descriptors. Repeated commissioning verifies these same bindings and
allows already used bounded payload bytes; it does not truncate content, expand
capacity, replace the root or clear unread/unknown work. Changed capacity or
blueprint requires a separately controlled migration. Unenrolled targets and the
UNCONFIGURED descriptor remain explicit for later setup stages.

The ownership check is cooperative. A suspended old actor may finish one previously
admitted immutable allocation after takeover; successors inspect that same ID.
This does not replace newer control state or authorize replay of unknown jobs.
There is no claim of instantaneous revocation of an already admitted external effect.

## Operation and rollback boundaries

Only the explicit setup port exposes creation. Normal authority access remains
READ/CAS; runtime receives no allocation/delete method. Tests instrument repeated
setup and ordinary lease renewal against further creation, verify IDs/inodes,
and fill existing capacity without allocating replacement objects.

Interrupted setup remains PREPARING/UNKNOWN and inspectable. No automatic cleanup
or shared-root deletion is provided. Removing even a proved unreferenced live
object requires a separate owner-approved scope. Tests use synthetic SDK services
and fresh task-owned private local directories; they do not qualify live Google
credentials, Windows ACLs, physical power loss, real remote provisioning or
production deployment. Those release/deployment gates remain separate.

Provider references: [Drive create-file and generated-ID restrictions](https://developers.google.com/workspace/drive/api/guides/create-file),
[custom properties visibility](https://developers.google.com/workspace/drive/api/guides/properties),
[Drive create](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/create),
[Docs batch update](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate).

