# Protected settings foundation qualification

Source: 5aa29c4fe64e45aa580534135c880d35fe36bc52.
Intent: RP-022-A001-0004.
Environment: actual Windows x64, Python 3.11.9, new synthetic private fixtures only.

Command: `python -m pytest tests/security/test_private_settings.py tests/security/test_private_settings_native.py tests/security/test_windows_credentials.py tests/security/test_windows_key_native.py tests/security/test_linux_credentials.py tests/security/test_linux_key_native.py -ra --basetemp=../rp22-foundation-fixture-001`.

Observed: **167 passed, 37 skipped in 0.55s**, exit 0. The 37 skips are 33 actual Linux key cases and 4 Linux-specific settings special-object/rename cases. Windows native settings operations and the 15 previously accepted Windows key cases executed. Linux native results remain unqualified until CI.

Reviewed invariants: current/previous revision preservation across a new adapter instance; conflicting writer refusal; exact complete staging recovery after interrupted first commit; no identity regeneration with malformed staging; copied-directory binding refusal; real exclusive lock contention/release; broad root/file/lock ACL refusal without repair; hardlink refusal; digest corruption preserved; explicit creation authority; closed error/repr/canary outputs. Transaction fixtures also verify counter exhaustion, nonfinite/oversized payload rejection, stale pending frame refusal and lost readback inspection without replay.

No failures observed. This is foundation evidence only. First-run model, credential persistence, setup UI, actual Linux settings qualification and activation integration remain unfinished; no RP022 acceptance checkbox is granted from this result. No real provider/root/key or deployment used.
