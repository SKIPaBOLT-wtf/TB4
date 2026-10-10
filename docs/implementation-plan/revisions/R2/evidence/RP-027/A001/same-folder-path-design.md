# RP-027 A001 — same-folder path design, unqualified

Intent: RP-027-A001-0134. Source reviewed: `a71954afb45c9e667ae1dd554b6b134fcf7c17c9`.
The exact132 CI source/head/runs remain pending in platform-import-repeat-started.json.
This is a read-only design outcome, with no implementation, physical move or accepted check.

## Verified source facts

FolderBinding uses a logical root UUID and domain UUID. FolderConfig separately pins
the absolute private server path and the directory/database/PERSIST-journal device/inode
pairs. Its real verify method checks current identities, owner,0700/0600 protection,
ext4/xfs, symlink/foreign-sidecar and size limits. Every ordinary FolderStore connection
locks the existing database inode, rechecks configuration and uses the same existing
SQLite table. There is no second authority or ordinary provisioning RPC.

FolderCommissioning seals artifacts with the root and artifact inode identities;
the authority handle binds root/database/journal identities and spec fingerprint.
Moving the same directory within its qualified filesystem preserves these identities,
logical spec, xattrs and contents. A pathname change alone must not become a new
logical root UUID, setup/bootstrap identity, database or catalogue allocation.
The ordinary helper accepts one protected static config and only READ/CAS.

Actual Maintenance/Effects/NativeCheckpoint already provide explicit fresh C1 resolution,
schema/source/profile/current role/capability/trusted-clock checks, native reservation
and shared UNKNOWN before external work. Pure inspection also supports real FolderSnapshot.
Their concrete folder composition and all subsequent relocation behavior still require
actual native Linux qualification; the existing Docs qualification does not establish it.

## Required next source units

1. Add a small closed protected two-path folder mapping and read-only resolver. Its
   creator must require actual fresh C1 resolution/current role/profile/pin/native
   reservation, exact original FolderCommissioning/FolderConfig/handle and distinct
   protected stores. Persist/read back the original and proposed private paths, parent
   identities, fixed directory/database/journal identities, spec/binding and transition
   before any physical operation. Use one pinned unreleased schema. Bounds remain
   under the existing private frame limit; no real deployment paths go to GitHub.
   The resolver checks only the exact two commissioned candidates and admits exactly
   one verified same original inode tuple. Zero candidates, aliases, contradictory
   candidates or changed fixed objects fail closed. These lookup facts grant no
   leadership, workload routing, cancellation or SDK replay.

2. Compose that resolver with the existing server helper through an explicitly
   commissioned protected optional pointer. Keep its default static behavior and
   closed READ/CAS transport. A client supplies no filesystem paths or provisioning
   action. Ordinary role reads and strict CAS locate the same sole SQLite authority
   while an exact path operation is unresolved; maintenance still gates ordinary
   dispatch. Lookup cannot require the moving controller's exclusive WAL lock, so
   use a distinct protected mapping store and operation WAL. Actual qualified
   FolderCommissioning/readback must follow the chosen fixed identity, retaining the
   same logical storage spec/handle and existing artifact seals.

3. Add a separately qualified native physical transaction. Require the actual
   shared current maintenance/effect/native proofs, one frozen destination, protected
   source/destination parents and one filesystem. Hold the existing database lock
   across final locked current-role/work/effect checks and one no-replace rename.
   Do not reacquire the same DB or native WAL lock through proof/lookup methods.
   Store exact PREPARED and INVOKING before the syscall. Exact before/after/conflict
   recovery inspects the original operation; an uncertain invocation gives no repeat
   permission. Preserve original effect owner/epoch/ID after takeover. Proven
   non-dispatch needs exact exclusive native evidence; no old-peer ACK is a role gate.
   Synchronize required directories and validate the same inodes/xattrs/raw authority
   and artifact data afterward. Separate local mapping recovery/confirmation from
   shared effect settlement and final C4 activation. Later rollback is another
   explicit monotonic operation, with no replacement or generation rewind.

The Linux man-pages rename(2), RENAME_NOREPLACE section (man7.org/linux/man-pages/man2/rename.2.html)
specifies a no-replace flag and same-filesystem limit. The
Linux man-pages fsync(2), directory-entry durability section (man7.org/linux/man-pages/man2/fsync.2.html) identifies
directory synchronization as necessary for directory-entry durability. Qualification
must exercise actual Linux calls in newly created owned ext4/xfs fixtures, retaining
uncertainty across interrupted replies/persistence. No mounted filesystem, router,
service account, running installation or unavailable local authority is changed here.

## Acceptance predicates for those units

Use actual Linux FolderCommissioning, ordinary closed helper/FolderStore,
protected native setup/checkpoint/effects/evidence, C1 resolution and source pin.
Prove exact directory/database/journal/artifact identities, xattrs and used contents,
canonical authority and all workload generations unchanged across path lookup and
eventual qualified rename. Prove old static clients fail safely and configured mapped
clients continue reading/renewing/first-CAS stale takeover during maintenance.

Cover before/after/no candidate, alias/symlink/replaced DB or journal, foreign sidecars,
unqualified filesystem, existing destination, changed parents, store alias, stale
profile/pin/config/owner, force request, clock/capability failures, unresolved shared
and native work, lock conflicts, native persistence cuts and uncertain rename reply.
No create/copy/delete/reset/overwrite/cross-device fallback, unknown replay or
persisted-readiness grant is permitted. Platform/native/RPC/full regression/frozen
and final C1-C4 gates remain necessary.

## Continuity

Only this design evidence is produced; no application/test/protocol/helper option or
runtime action exists from this unit. Keep132 unsettled until its actual three runs
are recorded. Then apply the smallest qualified resolver unit above, followed by
physical rename/effect recovery. Docs same-object catalogue rebind, final descriptor/
configuration/epoch/profile promotion and stale-cache/lease refusal remain separate
required RP-027 work. No new owner product-direction decision is inferred.
