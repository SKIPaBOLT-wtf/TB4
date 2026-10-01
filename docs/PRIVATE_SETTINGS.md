# R2 protected local settings foundation

This is the private storage foundation for RP-022, not a commissioned runtime
or a migration of installed v1 profiles. The first-run model and local setup UI
must apply a closed payload schema; the generic store does not make arbitrary
JSON safe to publish or appropriate to store.

An explicitly selected fresh leaf directory can be created only with local owner
authorization. Existing directories, files and ACLs are verified, never repaired.
The Windows parent must already be private to the current user. This is an
explicit preparation requirement; the program does not silently narrow another
application's directory ACL. Linux ancestors must be root/current-user owned,
not writable by others (the standard root-owned sticky directory exception is
permitted); the selected leaf is private. Supported storage is local NTFS/ReFS
on Windows, ext4/XFS on Linux64. Unsupported mounts are refused.

Every read/write holds a native exclusive process lock and verifies current
identity, directory identity, filesystem and file ownership/protection. Windows
checks token SID/session/logon, DACLs, fixed-volume canonical paths, reparse flags,
single links, and denies conflicting file sharing. Linux checks effective thread
credentials, groups/session/namespaces, pinned no-follow ancestor descriptors,
owner/mode/no POSIX ACL, single regular links and nonblocking advisory flock.
The Linux lock coordinates TB4 processes; it does not constrain arbitrary
native code running as the same user. Neither platform promises isolation from
a hostile administrator or another program with the user's full authority.

A frame contains one payload and its previous snapshot, a monotonic revision,
a digest and a binding to host/current principal/physical directory. Host binding
is derived privately from the standard OS machine identifier. It is not exported
as a device alias, report field, telemetry or development evidence. A digest
detects accidental corruption; it is not a signature against the local owner.
Copying files to another installation directory is not identity recovery.

Writes create settings.pending exclusively, flush, atomically replace
settings.json and read back exact bytes. An interrupted complete candidate may
be inspected and promoted only when its previous payload and next revision
match the current frame. A missing current file with any pending data cannot
create a replacement identity. Partial, corrupt or contradictory data remains
explicitly blocked and untouched. A lost readback is unconfirmed, not permission
to repeat an external action.

Rollback belongs to the stopped first-run workflow: inspect the preceding
payload, validate it under current rules, and save it as a new revision. It
must never roll back external provisioning, erase UNKNOWN operations, restore
an old WATCHDOG lease, renew stale observations or reconstruct missing secrets.
Production runtime release and activation remain separately gated.
