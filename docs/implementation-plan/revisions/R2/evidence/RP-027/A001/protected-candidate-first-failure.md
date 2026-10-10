# RP-027.C2 first targeted run failure

Source: `c323da611eb98de3966145e226679335976b3f22`; actual checkout: `43539cb4712e10d48d089a51b91f137d2f727b77`. One exact27-target run on WindowsX64, existing Python/offscreen Qt, fresh owned initially absent fixture root. Actual exit1 in60.934s:713PASS,3FAIL,4 Linux-only skips,720 cases. All683 previous predicates/statuses retained. Public-safe full cases and closed failure messages: `protected-candidate-first-cases.json`.

Three actual-native promotion-cut cases (transaction/archive/profile) expected only COMMIT_UNCONFIRMED; observed SETTINGS_STORE_UNAVAILABLE. Existing Windows/Linux native locked context managers preserve SettingsError and map other exceptions to that closed code (`private_settings_windows.py`, `private_settings_linux.py`). This establishes a new test expectation mismatch, not an application guard failure. The remaining exact pending-frame recovery/original-byte/no-send assertions in these cases were not reached and are not treated as passing.

Other new actual-first-run staged review/restart/history, saved readiness/arbitrary checker, lost credentials, metadata/access/readback/pin, rewritten archive/store alias, tampering/copy/native protection and default denied desktop activation predicates pass. Existing real Qt setup UI regression is included. No original profile/authority reset or live mutation occurred.

Register DEF-060; preserve failed artifacts privately. Next: read-only inspection of these same failed native pending frames, publish its actual facts, then fixture-only closed-code repair and recorded exact repeat. No C1-C4 check accepted or final recheck waived.
