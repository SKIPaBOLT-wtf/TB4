# Final combined qualification — failed plan-identity test

Sourceb4fd7c5158a14cdbb73eebd2b95f2b78947beddc; headb60ded298b109e6df59db2226a2647ffa385b5c6; all actual jobs checked out9bfcc503b52eba30bac299eb5eada5525a5b5996. All run/job outputs were read; no job remains running or its result inferred.

| Actual gate | Run/job | Result |
| --- | --- | --- |
| CI | 36945834818/110647641653 | FAIL exit1:1failed2324passed22skipped4knownDEF002xfail653.15s; nativeLinux43,protected34,loopback2 passed |
| Progress | 36945834809/110647641632 | SUCCESS:235passed10.52s,current/historyPASS20/64,onlyqualification0010pending,scanner clean |
| Desktop Windows | 36945834819/110647641742 | FAIL exit1:1failed2270passed91skipped4knownxfail752.53s; Qt71pass4POSIXskip,nativeWindows15,protected30pass4Linuxskip,loopback2,BALLPARK75,enrollment79 passed |
| Desktop Linux | 36945834819/110647641913 | FAIL exit1:1failed2344passed17skipped4knownxfail666.98s; Qt75,nativeLinux43,protected34,loopback2,BALLPARK75,enrollment79 passed |

Each full suite failed the same unchanged `test_export_and_every_gate_reference_are_current_plan_identities` literal YAML-format assertion. Both role builds, package/installer lifecycle and artifact publishing were SKIPPED on both platforms; there is no successful final artifact qualification. Linux native repaired original mutation regression passes inside the complete suite, but this does not accept the aggregate gates or any held step.

Old first qualification at6a9/a862/36917491747 and all earlier outcomes remain unchanged. Preserve four known strictDEF002 expected failures and declared native/optional platform skips separately. Read-only exact-source, semantic-format control and local current/history/scanner checks are supplementary evidence, never replacement full-suite success. Next: repair the proven validation-harness mismatch under a scoped INTENT, qualify it locally, then one new required matrix on the resulting exact final source. All21–25holds remain.
