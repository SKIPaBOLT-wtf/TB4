# Linux protected existing-key resolver

RP-021 selects read-only access to an explicitly owner-selected existing file.
It is an RP-006 LocalStore adapter, usable by a commissioned desktop or headless
process without an agent, desktop keyring, display or unlock prompt. Windows and
Linux reuse key_policy.py for installation/target/purpose/expiry/revocation and
fixed-use outcome handling; Windows imports and policy remain compatible.

## Enrollment and supported modes

Trusted local commissioning supplies the absolute key path, installation UUID,
target UUID and approved host-trust digest, allowed fixed purposes, expiry and
desktop/headless launch mode. Neither home-directory scanning nor SSH_AUTH_SOCK
is consulted. Only access_mode existing_key is supported. Agent, Secret Service,
automatic-store and interactive-unlock selections fail with STORE_UNAVAILABLE;
there is no fallback to plaintext configuration or another credential.

Selection and RP006 binding references are random, installation-local and kept
in process memory. Protected durable enrollment/recovery is a later RP022 gate.
A restart requires trusted enrollment again until that layer is implemented.
Key parsing, passphrase use and real authenticated fixed SSH execution remain
RP037. A selected encrypted file does not mean an unlocked usable SSH identity;
the fixed transport must reject unsupported/locked input without prompting.

Linux64 x86_64/aarch64, procfs thread identity and local ext4/XFS are the declared
native implementation scope. Actual CI qualifies its runner architecture only.
Other architectures/filesystems or missing kernel facilities fail closed. No
privilege escalation, ACL repair, ownership change or key import is attempted.

## Native boundary

The enrollment user is bound to real/effective/saved/filesystem UID/GID,
supplementary groups, POSIX session and user/mount namespaces. They are rechecked
before use. Desktop mode does not infer unlocked state from DISPLAY; it uses the
same explicitly authorized noninteractive file mode as headless operation.

Directory traversal holds no-follow directory descriptors. Ancestors must belong
to root or the selected user and not be writable by other users, except a
root-owned sticky directory such as the normal temporary directory. The immediate
key directory must be owned by the selected user and private. Access/default
POSIX ACL entries are conservatively rejected, including masked named entries.

O_PATH first checks the final object without opening a device/FIFO; the same
regular inode is then opened read-only through its held procfs descriptor.
A single-link, selected-user-owned0400/0600 file of1..65536 bytes on the qualified
filesystem is required. A bounded procfs lookup matches the held descriptor's
mount ID to its exact filesystem type, because ext2/ext3/ext4 share one magic
number. The native magic must also agree. Symlinks, devices, directories, hard links,
extended ACLs and unsafe components fail closed. No user path is hardcoded.

A nonblocking shared flock detects cooperative exclusive holders; Linux locks
are advisory, so they are not claimed as mandatory write protection. Stable
identity/size/timestamps and content digest bind the selected version. Reads are
bounded; changed source metadata, permission, path linkage or version invalidates
admission. The parent chain is checked again while the handles are held.

The fixed helper receives a borrowed anonymous memfd descriptor containing that
bounded snapshot, with private0600 mode, close-on-exec and WRITE/GROW/SHRINK/SEAL
seals verified. It receives neither the original path nor a public credential
value. The descriptor closes after the one callback. A concurrent external edit
cannot change the admitted snapshot. The mutable transfer buffer is cleared;
this is not a forensic erasure, no-swap or core-dump protection guarantee.

## Reports, trust and lifecycle

ExistingKeyStore rechecks binding, native identity, expiry/revocation, purpose,
target pin and held version before exactly one fixed FETCHER_STATUS or
FETCHER_START callback. The trusted runner must verify its actual endpoint and
honor its transport timeout. An injected verifier is not evidence of a live
authenticated connection. READY reports local resolver availability only.

Public output is the RP006 enum/boolean capability or use report. Exceptions,
key bytes, locations, user IDs, namespace IDs, target mappings and versions are
not exported. Unknown or malformed callback replies map to UNKNOWN without
automatic retry. Same-user trusted code and root are inside the local boundary;
this is not a sandbox for hostile native code.

Revocation/rotation removes or disables references and preserves external key
files. Install/uninstall has no credential copy/delete hook. Once an operation
has been admitted, later revocation does not retroactively undo its effects.
This does not add a WATCHDOG takeover acknowledgement barrier.

## Qualification and references

Portable tests cover modes, identities, purpose/trust, permission/version races,
expiry/revocation, raw/lost replies and canary-safe output. Actual Linux tests
exercise fd lifetime, permissions/ACLs, path aliases, locking, seals, rotation,
new-session rejection, cleanup and both declared launch modes. They skip only
off Linux; native prerequisites must succeed on Linux CI. Full Windows regression
covers the shared-policy extraction, and both platform packaging gates still
apply. No live installation, actual credential or network target is used.

API semantics:
- [Linux open/openat and descriptor flags](https://man7.org/linux/man-pages/man2/open.2.html).
- [POSIX access control lists](https://man7.org/linux/man-pages/man5/acl.5.html).
- [Anonymous memory files](https://man7.org/linux/man-pages/man2/memfd_create.2.html)
  and [file seals](https://man7.org/linux/man-pages/man2/F_GET_SEALS.2const.html).
- [Filesystem identity](https://man7.org/linux/man-pages/man2/statfs.2.html)
  and [filesystem user identity](https://man7.org/linux/man-pages/man2/setfsuid.2.html).
- [Python3.11 OS descriptor APIs](https://docs.python.org/3.11/library/os.html).

These references define mechanisms; source-linked native results establish the
tested platform scope. Later protected commissioning and actual SSH integration
must preserve this boundary rather than treating these fixtures as field proof.
