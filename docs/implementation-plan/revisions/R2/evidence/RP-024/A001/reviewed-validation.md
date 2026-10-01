# RP-024 A001 - reviewed exact-source qualification

Source: `87cf87f7fddf39ad53f5d41b5af5fadac8d84c5e`. Hosted PR trigger: `655ef653bf1702b3250c242eac582cd38ef5fa22`.
Every hosted job checked out `64e9d36148a0d37aa7799067066903b281b35d61`.
A fetched, read-only comparison of src, tests, skill, protocol, config, packaging,
tools, .github and pyproject.toml to the source returned exit 0. Later branch
changes were journal/evidence/navigation only. PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/33.

## Actual hosted results

| Gate | Run / job | Reviewed result |
| --- | --- | --- |
| Progress | 36848053871 / 110322841087 | 196 passed in 5.35s; current/history PASS, 23 VERIFIED, sole pending qualification 0037; public scanner clean |
| Linux full CI | 36848053980 / 110322841041 | 2197 passed, 22 skipped, 4 strict expected failures in 625.74s; native credential 33, protected first-run 34, native loopback 2 passed |
| Windows Desktop | 36848053932 / 110322841372 | desktop 71 passed/4 POSIX skips; native key 15, protected first-run 30/4 Linux skips, loopback 2, BALLPARK 75 passed; full suite 2153 passed/81 skipped/4 strict expected failures in 424.82s |
| Linux Desktop | 36848053932 / 110322841648 | desktop 75, native key 33, protected first-run 34, loopback 2, BALLPARK 75 passed; full suite 2217 passed/17 skipped/4 strict expected failures in 551.41s |

Both Desktop jobs separately built WATCHDOG and FETCHER. Their actual distribution
reports show PASS for bundle self-test/core imports, GUI smoke, setup GUI smoke,
and install/uninstall profile isolation for each role. Development artifact IDs:
Windows 11154991989, Linux 11154733254. Exact names include the tested checkout SHA.
Artifact ZIP digests respectively:
`ad188cdbe48bca016ef387566ecb1e3e2131eb854fc9109a530b72308325ec8b`,
`421ef35af05f2cc76cac529fa10eec175e3920454c2924df44a6b52321d5fb01`.
Artifact metadata was read back; both were unexpired. No downloaded artifact was
installed on the owner's system. Hosted job step conclusions and actual decoded
logs, including distribution reports, were reviewed rather than inferring them
from the overall workflow status.

## Invariant review

C1: the actual RP007 selection/boundary code pins setup guidance inside the verified
repository closure. Blank and partial choices are closed data, with known opaque
IDs and enums only. They neither trigger a scan nor grant approval. Local protected
frames retain exact choices. Restart fetches the original immutable catalogue,
instruction entry and full file-hash closure, while checking current eligibility.
The three reproduced DEF-041 metadata substitution cases reject; original-pin/main
advance and revocation cases preserve their intended semantics.

C2: a local explicit owner decision binds the exact candidate. The publisher checks
commissioned authority/marker/capacity, current owner and forced request, exact prior
revision and published discovery identities. It retains artifact/enrollment/discovery
fields and unrelated UNKNOWN work. One existing RecordMutation CAS updates the
selected catalogues, registry and settings together. Full serialized record budgets
are checked before saving the operation or writing. Every unchanged catalogue and
commissioning marker is guarded. Lost reply/restart only inspects the exact durable
plan, provenance, revision, digest and timing; it never repeats an uncertain write.

C3: proposal questions and draft/active views contain allowlisted opaque aliases,
roles/platform/launch/transport choices, timing, revision and status. They contain
no protected endpoints, hints, interfaces, topology, credential selectors or secret
values. Empty capability/observation proof is preserved; owner-selected transport
is not advertised as proven operational. Synthetic private-data canaries confirm
the boundary. Local Qt uses plain text and separate approval/publication controls;
pending restart enables only inspection.

C4: named cases cover blank deployment; partial/restarted choices; schema/enum/ID/
revision rejection; arbitrary private or instruction fields; wrong root/domain/
capacity/marker/artifact binding; malicious device text; revoked/missing/unreleased
guidance; protected-frame/pending-plan tampering; byte overflow; local save failure;
newer remote revision; discovery race; cancelled setup; and immediate stale/forced
takeover before and after durable intent. The 64-slot maximum-field codec roundtrip
fits unchanged RP009 budgets. A confirmed old operation may be read back after
takeover; new old-owner writes are denied without any sink acknowledgement barrier.

## Failures, platform and rollback limits

Local final focused qualification was 230 passed in 9.92s, with real Windows native
protected files and Qt. Earlier failing stimulus, progress-field, repair-hold and
catalogue-restoration attempts remain immutable (DEF-038 through DEF-041).
Hosted Progress independently proves corrected schema/holds/history, not a runtime
result. The four unchanged strict expected failures belong to historical DEF-002.
Platform skips retain earlier accepted POSIX/Windows-specific and unavailable optional
integration scopes. Crucially, both new BALLPARK files passed all 75 cases with
real Qt in each dedicated Desktop job; the base CI's missing-Qt skips are covered
there. No required RP024 case is accepted from a skip.

Prior active descriptor survives staging, failed local save and uncertain remote
publication. Cancellation, rollback and reconfiguration cannot erase pending or
confirmed provenance. Native protected-file restart confirms the same descriptor.
An interrupted unsent plan may remain conservatively UNKNOWN; no automatic resend.

Real instruction profile remains UNRELEASED with no eligible real builds; synthetic
eligible sources exercise the verified ports. Default activation remains denied.
Trusted production adapters, integrated WATCHDOG GUI (RP053), coordinated release
(RP061), ARM64 and real deployment/topology qualification remain later gates.
RP029 covers ongoing descriptor evolution. Legacy PARK_MAP and installed SKILL
were not migrated. This acceptance is isolated implementation qualification, not
live deployment permission or proof of remote target enrollment/capability.
Already admitted external effects may overlap takeover; no retroactive cancellation
or all-sink barrier is claimed.

Privacy review: PUBLIC_SAFE_REVIEWED. Only synthetic fixtures, public source SHAs,
workflow IDs and sanitized assertions are recorded. No deployment data or credentials.
