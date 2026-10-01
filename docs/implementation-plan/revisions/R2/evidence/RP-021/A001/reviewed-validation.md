# RP-021 A001 reviewed acceptance

Source: 16e403e7b76b1e9bc2e4e8946d140ddb8778db3c.
PR 30, initial test head 0517da7cddcb68520b01cb3bea6654102e6da3cd.
Scope is a selected existing-key adapter, not live SSH or installation.

## Invariant review

C1: LinuxKeyStore requires trusted owner-authorized path/installation/target pin/
purposes/expiry and explicit desktop/headless mode. Native user/session/groups/
filesystem credentials and namespace checks bind local admission. Directory FDs
and an O_PATH final anchor prevent pathname aliases/device opens; the same inode
is reopened read-only. Exact owner 0400/0600, single link, size, conservative ACL,
mount identity/type and content version are required. There is no home scan or
embedded user path.

C2: existing_key has no daemon, agent socket, display or unlock prompt dependency.
Unsupported agent, SecretService, auto and interactive-unlock modes refuse
explicitly. Desktop mode does not claim an unlocked desktop. No plaintext config
fallback or external key mutation occurs. Source reads are bounded; fixed-runner
transport deadlines and actual authentication belong to RP037.

C3: portable cases cover all identity dimensions, permissions, purpose/trust,
expiry/revocation/rotation, acquisition races and lost/raw callback replies.
Native tests exercise real Linux owner modes, POSIX ACL rejection despite a
zero mask, advisory locks, symlinks/hardlinks/FIFO/directory/size, path/content/
permission changes and a real fork/setsid denial. The source lookup is held,
snapshotted and sealed; advisory flock is not called mandatory file exclusion.

C4: fixed callback receives only a private noninheritable sealed-memory
descriptor and target trust context; no original path or credential value in
public reports. WRITE/GROW/SHRINK/SEAL flags prevent admitted snapshot changes.
Real fixed callbacks verify synthetic bytes internally and return closed states.
Failure/lost reply closes the descriptor and produces UNKNOWN, never auto-retry.
Revocation preserves external files. Same-user trusted code/root remain trusted.

## Shared policy and retained failures

The common ExistingKeyStore is extracted from the accepted Windows policy;
Windows UserSession, imports and public selection interface remain compatible.
All prior 86 RP006/Windows focused cases and hosted Windows native gate cover it.
No purpose, permission, target-trust or unknown-outcome check was weakened.

DEF-027: original size-fixture automatic ID exceeded the Windows 32767 environment
limit even for a skipped Linux test. Retain 138 passed / 32 skipped / 1 error, 0.50s, exit 1.
Explicit empty/oversized IDs change display identity only, preserving inputs
and assertions. Corrected 156 passed / 33 skipped, 0.33s, exit 0 proves the Windows issue fixed.

DEF-028: 0xEF53 alone also identifies ext2/ext3. The correction pairs native magic
with the held fd's bounded procfs mount ID and exact ext4/XFS entry. Eighteen portable
parser cases reject unsupported types, missing/duplicate/malformed/oversized
tables and mismatched magic. Actual tmpfs fixture rejection supplements it.
No ext2/3 mount or claim of field qualification was invented.

## Privacy, scope and rollback

Full node collection: 1912 in 0.72s is retained separately. Public scanner and
source diff pass. Published evidence contains no actual credentials, user paths,
namespace values, topology or raw environment/provider output. A connector
readback interruption was recovered at the same immutable candidate 8858794b
with all 16 paths and branch ref, without replaying a write or test.

Selection/binding metadata remains process-local; durable protected enrollment,
key parsing/passphrases and real authenticated helpers remain later gates.
Implementation accepts Linux64 x86_64/aarch64 with qualified ext4/XFS; actual
native runner architecture is the tested scope, not an ARM64/XFS field claim.
Memory seals and zeroed transfer buffer do not promise forensic erasure, absence
of swap/core dumps or hostile-code isolation. Admission checks cannot undo an
already admitted action. WATCHDOG availability-first CAS takeover is unchanged.
Rollback revokes only introduced references, closes owned descriptors and
preserves external keys/profiles. No installed runtime was migrated or launched.

## Confirmed platform and package receipts

All final jobs used checkout d0f5567a10f4fd6e204ac4d0acc07bfceed6822e,
tree 9c7d883fecff5c90d7cf118118af4b438a8a1f75, with parents ownership
415008b180cb2c0b97bdff40c8e21a066d6dc6b1 and PR head
0517da7cddcb68520b01cb3bea6654102e6da3cd.

- CI 36818084703 / job 110227442569: native Linux 33 passed in 0.12s;
  full 1893 passed, 17 skipped, 4 strict existing DEF-002 xfails in 401.64s.
  The 17 skips are 15 native Windows cases and 2 unavailable GUI modules.
  Required isolated Linux SSH tests executed under the existing CI prerequisite.
- Progress 36818084690 / job 110227443540: 172 passed in 4.77s;
  ledger (20 previously verified), append-only history and scanner pass.
- Desktop 36818084633 / Linux job 110227442123: GUI 68 passed in 2.24s;
  native Linux 33 passed in 0.18s; full 1904 passed, 15 native Windows skips,
  4 strict known xfails in 532.32s.
- Same Desktop / Windows job 110227442399: GUI 64 passed, 4 platform skips
  in 6.99s; native Windows 15 passed in 0.21s; full 1847 passed,
  72 Linux/POSIX skips, 4 strict known xfails in 526.47s. The 72 skips combine
  prior 39 platform cases and 33 new Linux-native cases.
- Both platform jobs built both roles, then reported PASS for actual
  bundle_self_test, gui_smoke and install_uninstall_profile_isolation.
  No required full/package job remains running.

Artifact metadata below is provider-reported, not downloaded, independently
rehashed or deployed:
- tb4-desktop-Linux-d0f5567a10f4fd6e204ac4d0acc07bfceed6822e; ID 11142543129; 314192774 bytes; sha256:e0afa7ed1a853bfb1166a0d6a764e42fbe3503db7220cb5d4633ba747efa0bae
- tb4-desktop-Windows-d0f5567a10f4fd6e204ac4d0acc07bfceed6822e; ID 11142264075; 120727565 bytes; sha256:e93d442437a2a6ed5cb7104ffaaa94b8a8827844e8aae31503e8cba64442d93b

Local preaccept source comparison at ac813e7085567329042aaa76216f1a169598565e:
src/tools/tests/workflows/protocol/config/packaging/skill are byte-identical to
source16e403e7 in both current branch and the exact CI merge checkout; diff
check passes. The working tree is clean and main remains the ownership base.
Final receipt/history validation and exact-head merge are a separate following
gate; DEF-027/028 remain OPEN with all revalidation holds until that completes.
