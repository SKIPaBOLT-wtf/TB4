# Atomic first-run credential integration

Source: a3309d8606c22126481f18ae200481f823be2003.
Intent: RP-022-A001-0021.
Actual Windows x64/Python3.11.9 with fresh synthetic private files only.

Command: `python -m pytest tests/security/test_first_run.py tests/security/test_first_run_native.py tests/security/test_credential_persistence.py tests/security/test_credential_persistence_native.py tests/security/test_setup_credentials_native.py tests/security/test_private_settings.py tests/security/test_private_settings_native.py -ra --basetemp=../rp22-integration-fixture-001`.

Observed: **93 passed, 4 skipped in 0.96s**, exit0. The four skips are Linux special-object/rename cases. Actual Windows model/credential restart and all seven new composition tests executed.

Reviewed: metadata and selected opaque references commit in one protected expected-revision transaction; fresh native resolver restoration retains installation/handle and original selected file version; changed key refuses; revoked binding stays revoked across restart and cannot be rolled back, unrevoked or dropped from a later image; revocation is still persistable while external operation status is UNKNOWN, without new authority or changing its binding; conflicting real lock or mismatched reference prevents either half of the update. Synthetic key bytes stay outside settings and reports.

The preceding exact RP019 verifier source passed its full maximum-capacity regression in the model run; it was unchanged in this integration. Those slow tests are not duplicated locally without a source change and remain part of required CI.

No live credentials/provider/runtime. UI, Linux and full platform/package gates remain outstanding; RP022 stays IN_PROGRESS with no accepted checks.
