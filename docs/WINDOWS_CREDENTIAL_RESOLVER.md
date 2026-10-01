# Windows protected existing-key resolver (RP-020)

The selected RP-020 implementation is read-only integration with an explicitly
selected existing key file. It is not a new vault, key importer or credential
discovery service. `WindowsKeyStore` implements the accepted
[RP-006 contract](CREDENTIAL_RESOLVER_CONTRACT.md); `WindowsKeyNative` supplies
actual Windows token, file-handle and security-descriptor checks. Neither module
is connected to legacy desktop profiles or installed automatically.

## Commissioning and binding

A trusted local commissioning controller, already authorized outside any remote
request, supplies the installation UUID, selected absolute path, target UUID,
current pinned target trust, exact FETCHER_STATUS/FETCHER_START purposes, expiry
and whether an active unlocked interactive session is required. An explicit
noninteractive selection still binds the current user SID, Windows session ID
and logon authentication ID. Another logon requires authorized re-enrollment.
A boolean copied from remote JSON is never commissioning authority.

Selection first verifies the actual key. The returned random `wk_` reference
stays local; the RP-006 resolver then enrolls its own opaque `cr_` binding.
The selected path, identities, native handles and content/file version are never
included in public capability reports, repr output or provider errors.
Selection metadata is currently process-local, matching RP-006. The later
commissioning integration must protect any durable binding store and explicitly
re-enroll after restart; this adapter never silently reloads another profile.
Missing enrollment reports ABSENT, never inferred READY.

## Native Windows boundary

Supported native scope is Windows 10 or later, x64, a fixed local NTFS/ReFS volume
with persistent ACLs, and a nonempty key of at most 65,536 bytes. Unsupported
stores fail closed. There is no network/UNC path, device namespace, alternate
data stream, wildcard, relative path or fallback store. A final handle path
different from the selected path is rejected, including junction redirection.
Directory, reparse/offline/cloud-placeholder and multi-hard-link files are refused.

The selected file is opened OPEN_EXISTING with GENERIC_READ and READ_CONTROL,
only FILE_SHARE_READ, and a non-inheritable handle. No creation, write, delete,
ACL repair, privilege adjustment or elevation exists in this adapter. The held
handle prevents compatible Windows opens for writing or deleting/replacing that
file during use. Its final path, volume, file identity, size, content digest and
last-write time form private version evidence; changed material requires a new
explicit selection, even if a caller restored the last-write timestamp.

Ownership must equal the enrolled user SID. A missing/NULL/invalid or unrecognized
DACL is denied. Only ordinary allow/deny ACEs are accepted. Applicable nonzero
allow ACEs may name that user, SYSTEM or local Administrators; other trustees
are denied conservatively even if the requested mask appears harmless. Windows
also enforces the actual requested read access. Administrators, SYSTEM and trusted
code under the same user are part of the local trust boundary; this is not a
defense against privileged memory inspection, kernel compromise or a malicious
same-user process rewriting its own policy.

Every capability/use checks the current process user/session/logon and rejects
thread impersonation instead of accidentally using the process identity. When
interactive use was selected, WTS must confirm an active unlocked session.
A missing session service/unknown provider response is unavailable; the adapter
never displays a prompt, unlocks a desktop or logs a user in.

Each use reacquires and validates a held file, compares the selected and inspected
versions, rechecks revocation, time, identity/session, purpose and current target
trust, and rechecks the held file permissions/identity before dispatch. The
in-process lock serializes selection revocation and dispatch admission. Content
sharing protection stays active through the fixed callback. OS ACL/session/trust
facts are admission checks, not an atomic cross-system revocation transaction:
an already admitted external effect is not retroactively stopped by expiry,
session lock or another controller. No global ACK barrier is added to WATCHDOG.

## Fixed helper and outcome boundary

The injected trusted runner has exactly `verify_target(target, pin)`,
`fetcher_status(key, target, pin)` and `fetcher_start(key, target, pin)`.
It receives a borrowed native handle only during the callback, not an arbitrary
command string. It must check the commissioned protected endpoint mapping before
use and authenticate that same pin on its real connection. Host authentication
and actual fixed Windows/Linux transports remain RP-036/037 acceptance gates;
the synthetic runner is not evidence that those integrations already exist.
READY means the local resolver is available; SUCCEEDED is only that callback's
closed completion result, not independent FETCHER readiness.

There is at most one callback per invocation. Provider exceptions, lost replies
and malformed callback results become UNKNOWN without raw text or automatic
replay. Failures before admission do not invoke a helper. Reports retain only
RP-006 enums and booleans. The mutable temporary native read buffer used for
hashing is zeroed before release; Python/OS memory hygiene is not a promise of
forensic erasure or protection from an already privileged process.

## Tests, lifecycle and rollback

Portable policy tests cover identity, session, interactive availability, expiry,
purpose, target trust, permission/version races, rotation/revocation, malformed
providers, lost acknowledgements and canary-free reports. Actual Windows tests
use only fresh synthetic files: owner/DACL, broad and NULL DACL rejection,
exclusive sharing, denied write/delete access, content and file replacement,
missing/oversized/empty files, hard links, impersonation rejection, WTS response
typing, handle lifetime and preservation of unrelated material. Linux explicitly
skips native Windows tests; Windows Desktop CI runs them in its complete suite.
Tests do not lock a real desktop, create accounts or inspect existing credentials.

The adapter has no install/uninstall hooks, key copy/delete operations or profile
migration. Existing packaged installation/uninstallation regression gates remain
required. Rollback revokes/removes only newly introduced local metadata, reports
the capability unavailable and leaves selected or unrelated credentials intact.
Provider-side revocation is a separate authorized operation.

## Primary API references

- [CreateFileW access, sharing and OPEN_EXISTING](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).
- [Handle-based GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo).
- [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation).
- [Volume capability checks](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew).
- [WTS session state and lock flags](https://learn.microsoft.com/en-us/windows/win32/api/wtsapi32/ns-wtsapi32-wtsinfoex_level1_w).
