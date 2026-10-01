# RP-020 A001 reviewed acceptance

The selected implementation is read-only existing-key access for Windows10+ x64
on a fixed local NTFS/ReFS volume. Source46632bdf2648feacb3b17641e9b09811ad37ca1c
includes the final explicit-owner synthetic fixture and early native CI gate.
Production src, development ledger and its tests remain byte-identical to
5cf22faf6c009435e8c25343afcf9493f721904d. Runtime key source itself is unchanged
since bc3b5a42c66defebda12255b407b76b6b9e404e6.

## Invariant review

C1: WindowsKeyStore.select has explicit owner-authorized commissioning inputs;
no home-directory discovery, imports, persisted plaintext config or actual key
mutation. The opaque selection is installation-local and wrapped by RP006's
separately opaque binding. Native key reads are bounded to64KiB.

C2: user SID/session/logon identity and optional active/unlocked WTS admission,
thread impersonation rejection, owner and conservative DACL allowlist, fixed
local filesystem, final path/reparse/link checks and identity/content version
are enforced. A non-inheritable read-only handle denies ordinary writer/delete
sharing through the fixed callback. Purpose/target pin/expiry/revocation are
rechecked with the held handle. The trusted runner must still authenticate its
actual endpoint in RP036/037; an injected boolean is not a live host proof.

C3: actual native Windows cases cover owner/NULL/broad DACL, exclusive lock,
denied write/delete sharing, changed material with restored timestamp, file
replacement/missing/size/hardlink, impersonation and borrowed-handle lifetime.
Portable cases cover wrong user/session/logon, interactive unavailable, purpose,
target trust, permission/version/expiry races, revoked/rotated selections,
provider exceptions/raw results and unknown acknowledgements without retries.
Canary assertions cover public enums/booleans and hidden private repr fields.

C4: no install/uninstall hook, external key copy/delete or legacy profile migration
exists. The build includes tracked project source; existing both-role package
acceptance checks actual self-test, GUI smoke, install/uninstall and retained
profile markers. Native revocation separately proves selected and unrelated
synthetic files remain byte-identical. This is not a deployed enrollment.

## Retained failures and provenance

DEF025: early RP020 action IDs were lowercase. Existing validation correctly
failed. Exact original records remain an unchanged byte prefix; explicit
case-only read-view corrections preserve grouping, source/scope and actual
outcomes.26 negative/positive regression cases guard collisions, renames, mixed
or repeated corrections, future malformed rows and all other invalid fields.
The CRLF publication follow-up is retained; four-file normalized byte/three AST
proof and clean final base diff are documented. No schema/history gate waived.

DEF026: initial hosted Windows run failed8 newly-created fixture checks before
helper admission. The fixture had set DACL without an explicit owner. Only the
synthetic test security descriptor now sets OWNER and DACL; production strict
owner enforcement remains unchanged. See original windows-ci-failure.md and
final hosted owner equality evidence. Never erase or call the initial run green.

## Scope and rollback

Current selection/binding metadata is process-local. Protected durable enrollment,
real authenticated fixed transport integration and any live deployment remain
later plan gates. READY denotes local resolver availability, not FETCHER readiness.
OS/session/ACL/expiry observations are admission checks; already-admitted effects
are not retroactively revoked. Same-user trusted code, SYSTEM and administrators
are inside the local trust boundary. No global WATCHDOG takeover ACK barrier.
Rollback removes/revokes only newly introduced metadata and preserves existing
keys. No actual credentials, topology, profiles, services or live root were used.

The private archive's stale navigation references were independently updated and
remotely read back; that documentation maintenance is not product acceptance.

## Exact observed validation

Windows Python3.11 local final86 focused tests passed in0.18s; native15 cases
ran against fresh synthetic files. Local owner diagnostic true/true; final
collection1809 nodes in0.68s is preserved in final-collected-tests.txt.
Earlier byte-identical production full Windows:1765 passed,41 skipped,
4 strict expected DEF002 failures in535.35s, exit0. The41 skips are33
Linux folder/server/SSH cases,6 other POSIX cases and2 absent GUI modules.
Final source changes only synthetic native fixture and CI qualification.

Final PR head2727f003f40498866c2af70a08419a48b8b8716b,
checkout50f12b51e141a162a58c9cbab677df07d550867a,
treefa759fca5946247145c9dbfeca22314e23ef36d6:
- CI36814823520/job110217497817 PASS:1790 passed,17 skipped,4 xfailed,
  293.12s.15 Windows-only cases and2 absent GUI modules skip. Required isolated
  SSH fixtures actually execute on Linux.
- Progress36814823641/job110217498190 PASS:172 developer tests in7.36s;
  ledger/history/public scanner pass.
- Desktop36814823543 Linux job110217498005 PASS: GUI68 in3.46s;
  full1801 passed,15 native-Windows skips,4 xfailed in380.22s.
- Same Desktop Windows job110217498195 PASS: GUI64 passed,4 platform skips
  in2.68s; native15 passed in1.40s; full1777 passed,39 Linux/POSIX skips,
  4 xfailed in716.70s.
- Hosted native diagnostic: default_owner_matches_user=false,
  selected_owner_matches_user=true. This establishes the fixture-default-owner
  cause and verifies the correction without relaxing production validation.
- Both platform jobs build both roles and report PASS for actual bundle self-test,
  GUI smoke, install/uninstall and profile isolation. All required jobs completed.

Artifacts are provider-reported metadata, not downloaded/rehashed or deployed:
- tb4-desktop-Linux-50f12b51e141a162a58c9cbab677df07d550867a; ID11141575951; 314185833 bytes; sha256:f0b31b32de4e19b2a873d1da6455668659d9b950a2e2000edcc66bc1e0b7d9c0
- tb4-desktop-Windows-50f12b51e141a162a58c9cbab677df07d550867a; ID11141482402; 120721293 bytes; sha256:a1e52a858867ee4c02afb8a51186d810ef2f7a3c2a3cd2c7a567d0f3de5320d1

Local final preaccept at9fe27ba746b996f34e0155e3b0d1e08848ad99bb:
source equality against46632bdf for src/tools/tests/.github, base diff check,
ledger64steps19previouslyverified and public scanner all exit0. Sole pending
INTENT0032 is closed by this reviewed result. No source changed after the
final CI checkout. Historical failing runs and corrections remain recorded.
Final receipt/merge validation follows separately; DEF025/026 and acceptance
holds remain open until that final gate and main merge succeed.
