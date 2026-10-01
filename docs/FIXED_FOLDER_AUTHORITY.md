# Optional fixed-folder control authority

RP-018, unreleased R2. Default native Docs and installed v1 profiles are unchanged.
This module implements the **control authority** interface used by RP-015/016/017.
It does not emulate the legacy rename-based DriveBackend.

## Selected mode and one-root contract

The optional mode is FOLDER_SQLITE_V1: one Linux server-local private directory,
one existing authority.sqlite database and its existing persistent rollback
journal. One closed one-row table holds the canonical RP-009 document (maximum
512 KiB), root/domain UUID and monotonic revision. Clients use a fixed per-call
helper, normally through an already authorized SSH forced command. SQLite lives
only on that server's local filesystem; clients never open it over SMB/NFS.

The rollback journal contains recovery pages, not a second coordination authority.
Ordinary READ/CAS requests cannot provision, list, select a path, execute a command,
create a document or fall back to native Docs/local sync. Artifact payload slots
are separate fixed data capacity in RP-019/040/048, as for the RP-015 Docs control
adapter. This step supplies their shared descriptor authority, not payload IO or
a complete commissioned deployment. No root selection or migration is implicit.

| Mode | Control adapter decision |
| --- | --- |
| Linux local ext4/xfs behind the fixed helper | Eligible for explicit qualification/commissioning; tests record the actual filesystem used |
| Windows/Linux client using a commissioned fixed helper | Protocol/process port supported; actual endpoint/host/key/access must be qualified |
| Direct SQLite on SMB, NFS, FUSE, cloud sync, overlay, tmpfs or unrecognized filesystem | Refused, never promoted from apparent local visibility |
| Native Docs requiredRevisionId | Existing selected default, independent adapter; no automatic mode switch |
| Raw Drive file precheck/update or Drive sync mirror | Not an authority CAS |
| LLM with only a Drive connector for a folder-selected exchange | Activation refused; it needs an authorized adapter to the same root/domain |
| Windows/macOS as this folder server | Not implemented by this selected mode |

Only one mode is selected per commissioned domain. Public UUID fixtures are
synthetic; real paths, OS object identities, endpoint/credential/host-key bindings
remain protected setup data. Installation must obtain and persist the exact
root/domain binding and pinned directory/database/journal identities. Missing,
renamed, aliased, replaced or inaccessible objects fail closed. No guessed path,
new root or replacement journal is created by normal operations.

## Publication and ownership

Each helper call checks Linux filesystem type, exact object identities, private
ownership/modes (0700 directory, 0600 files), no symlink/hardlink file, bounded
sizes and absence of foreign WAL/SHM. SQLite opens mode=rw, then EXCLUSIVE locking,
PERSIST journaling, FULL synchronous writes, memory-only temporary storage and a
512-page ceiling at 4096 bytes/page. Schema, root/domain and canonical contents
are checked. Only one row exists.

CAS obtains a database transaction and compares the revision there. A successful
commit increments it exactly once. A concurrent busy lock is unavailable, not
evidence of a revision conflict. A stale revision after the winner releases is
rejected. Accepted writes require readback; missing/malformed/lost replies remain
UNKNOWN and use RP-015 INSPECT reconciliation, never blind replay. A helper
failure after transaction start is conservatively UNKNOWN.

The same RP-016 leadership and RP-017 dispatch rules apply: stale ownership can
be claimed immediately by the first successful CAS; force requests stop an
incumbent's next checked transition, and the requester can claim without any
peer/sink acknowledgement. Computer name is display metadata. Unknown old jobs
remain retained; this cannot revoke an external action already admitted.

## Fixed helper and access boundary

folder_helper accepts one private --config argument from trusted commissioning.
RPC has a closed flat envelope: version, mode, root, domain, fresh nonce,
operation READ or CAS, and (CAS only) expected revision plus base64 canonical
document. There are no caller-selected paths/commands. Request/response bounds
are 1 MiB, canonical body 512 KiB; duplicate keys, extra fields, wrong nonce/root,
nested structures and non-finite JSON are rejected. The helper has an eight
second alarm; the process port uses at most fifteen seconds, no shell and no
retries, bounded output, and discarded stderr. Stable errors never include
private provider messages or file contents.

FolderAccess is a trusted setup attestation, **not a security token** and not an
LLM-provided boolean. Commissioning must test both role and LLM access against the
same fixed helper/binding before constructing it. Missing/wrong/false attestation
blocks the adapter before any IO. The protected resolver must supply an authorized
fixed argv with noninteractive authentication and pinned host trust. Shared
records cannot replace argv or the binding. Local Python callers and the trusted
helper account are not sandboxed by these types.

The isolated OpenSSH test uses two generated client keys, a generated host key,
pinned known-hosts, loopback-only binding and a forced helper. No key material is
published. Its StrictModes=no accommodates pytest's temporary ancestor and is
**test-only**, not a production setup instruction. CI requires this fixture;
missing tools or unsupported server storage fail that gate. Other platform skips
are reported as untested server modes, not passing coverage.

## Durability, limits and later gates

The interruption test kills only its newly created writer process after dirty
database pages have spilled. Reopen must restore the last committed revision/body
using the same database and journal identities. A missing journal is refused,
not recreated. Inventory checks cover normal writes, rollback, independent clients
and remote reconnect.

SQLite FULL durability depends on correct OS/filesystem/device flush behavior.
Process-kill recovery does not prove sudden power-loss survival, hardware cache
behavior, remote machine durability or multi-host disaster recovery. See
[SQLite atomic commit](https://sqlite.org/atomiccommit.html),
[journal modes](https://sqlite.org/pragma.html#pragma_journal_mode) and
[network filesystem caveats](https://sqlite.org/useovernet.html).
The journal and database must reside on the same commissioned local filesystem.
xfs eligibility is not a claim that this test runner exercised xfs.

Trusted administrative replacement, relocation, permission changes or restore
must happen offline under a separate authorized maintenance/migration procedure.
Identity checks detect drift but are not atomic protection against a malicious
same-account administrator racing filesystem replacement. Keep the directory out
of sync/backup-restore writers while active. Do not remove a hot journal, run
VACUUM, change journal mode or reset revision to repair an unknown operation.

RP-019 supplies resumable explicit provisioning, fixed artifact allocation and
normal-operation create/delete instrumentation. RP-020/021/025 supply protected
credential/host bindings; later integration/topology/release gates qualify real
installations and the actual LLM connector. No installed runtime, home network,
NAS, credential store or live shared root was changed for RP-018. Until these
gates pass, this is a tested adapter primitive, not a released deployment mode.

