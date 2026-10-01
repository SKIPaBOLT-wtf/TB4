# RP-025 focused qualification

Exact runtime/test source: `86d4d32598616b935a7b8b2623d0c3a28e65767d`. Local source-safe synchronization verified clean at checkpoint `afb11e326a05724bee1927a3e558ddfced682ad3`. Test INTENT `RP-025-A001-0019`; actual local session22018.

| Gate | Actual result |
|---|---|
| Dedicated profile/enrollment files only, freshbase06 | **72 passed, 11.13s, exit0**, no skip/xfail |
| Original seven-file profile/enrollment/BALLPARK/discovery/setup/native credential regression set, freshbase07 | **221 passed, 21.69s, exit0**, no skip/xfail |
| Public security scan | clean, exit0 |
| Full branch whitespace/diff check against origin/main | exit0 |

Python UTF-8, actual local Windows process and Qt offscreen were used. Tests exercise separate protected native WATCHDOG/FETCHER settings roots/restart, actual local native key ownership/credential-pair boundary with explicitly synthetic target-verification probe, fresh two-device synthetic commissioning, strict atomic single-catalogue registration/update/revoke, disabled capabilities and effective runtime timing/interpreter facts, duplicate/reinstall/identity/alias/capacity/stale/future failures, durable private-save failures/recovery, lost-reply inspection only, cancellation, peer/pin/record tampering and the existing stale/force takeover without acknowledgements. No real remote endpoint, credential-use command, live migration or installed-runtime activation occurred. New trusted-peer and authenticated transport ports remain explicit integration dependencies; execution_authorized is always false in the projection.

DEF-042 import ordering and DEF-043 fixture prerequisites were re-exercised without weakening prior assertions. All failed source/evidence remains preserved. C1-C4 and defect resolution remain on hold until complete source review, current/history validation and required hosted Linux/Windows native/frozen gates. Counts alone are not acceptance.

Raw synthetic logs remain task-local at work/rp25-dedicated-06.log and work/rp25-focused-07.log. Next action: validate progress/history and review exact source/invariants, then create and attach one draft PR to collect required hosted qualification.
