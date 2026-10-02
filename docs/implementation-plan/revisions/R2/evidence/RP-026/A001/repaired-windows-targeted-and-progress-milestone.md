# Repaired-source Windows targeted and Progress milestone

RP-026 / A001; INTENT RP-026-A001-0045 and STARTED0046. Source 6b1a4d19d5e4f349823b4367b5e19b4b7fe8a657. Actual local checkout e9e825be23a39e23c435b9e10076e302e330494e; Windows win32, Python 3.11.9, fresh run rp26-targeted-004. This milestone leaves INTENT0045 unsettled.

The exact 15 test paths/procedure are recorded in INTENT0045. Target helper ran actual pytest with offscreen Qt, a new isolated fixture root and JUnit; then SKILL validation, current ledger, full base-history ledger, public scan and diff check. Actual gate return codes (not the shell cleanup exit) were all zero:

| Gate | Actual result | Seconds |
|---|---|---:|
| targeted pytest | 365 collected, 343 passed, 22 platform skips, no failures/errors/xfails | 28.015 |
| repository additional SKILL | PASS | 0.078 |
| current ledger | PASS, 25/64 verified, INTENT0045 pending | 14.187 |
| history from main 33e7aeb1896df4709ee9cdca7134532bc536aeb5 | PASS, published history preserved | 26.750 |
| public scanner | PASS | 6.532 |
| diff check | PASS | 0.062 |

The adjacent closed JSON preserves every collected case ID/status, including all 22 actual skips. Skips cover four Linux-only native protection cases and 18 Linux installer cases; they are not counted as Windows passes and need actual hosted Linux coverage. All ten real native table cases passed, including actual Discovery.observe with full current-owner read, write/stage/promote refusal, escaped context, other-thread contention and refusal/exception preserving pending UPDATE. All targeted schema, helper, Qt, discovery, BALLPARK, enrollment and accepted native/setup regressions passed.

Hosted Progress run37025861218/job110900190859 completed SUCCESS: 235 development cases passed in12.30s plus current/history/public guards. Its actual checkout 1cf964a40d2102bec0de52da22effd72be39cecd has Git tree 7c0552a6ccef6f83c8d56a711e6ab839d2d48f75, identical to qualification head e9e825be23a39e23c435b9e10076e302e330494e. Verified parents are main33e7aeb1896df4709ee9cdca7134532bc536aeb5 and that qualification head. Local Git diff from implementation source to qualification head contains only immutable documentation/progress paths; app/test/catalog/attribute bytes are unchanged.

CI37025861081 and Desktop37025860808 remain in progress. Full hosted Linux/Windows results, actual per-job checkouts, both role builds/distribution smoke/installer checks and artifact metadata are not accepted yet. DEF-049 through DEF-053 and C1-C4 remain held. No deployed profile/network/table, runtime grant or live migration was tested/changed; native fixture bindings/raw logs remain local.

The first prospective receipt was rejected by the unchanged public-data guard before publication because two instruction-injection test IDs contain adversarial URL parameters. Their public projection retains the exact function, full case SHA256 and observed status; the exact original IDs remain local. No raw value or failed test was removed, and no repository history was mutated by that rejected preparation.
