# Exact pending setup reopening regression

Source: 5e3617a42ac732cb3d0d1ff7b5521fa354e0c3a5.
Repair: RP-022-A001-0034; validation: RP-022-A001-0036.
Actual Windows x64/Python3.11.9, Qt6.11.2, fresh synthetic private fixtures.

Command: `python -u -m pytest tests/security/test_first_run_native.py tests/security/test_private_settings.py tests/security/test_private_settings_native.py tests/security/test_first_run.py tests/security/test_setup_credentials_native.py tests/desktop/test_setup_ui.py -ra --basetemp=../rp22-repair-fixture-001`.

Observed: **80 passed, 4 skipped in1.19s**, exit0. Four skips are Linux-specific special-object/rename cases. Actual desktop.open_setup recovery cases executed: complete first identity staged before lost promotion reopened with the same installation UUID and setup nonce; interrupted cancellation preserved CANCELLED and original UNKNOWN operation history with only one callback invocation; repeated reopen retained identity. Partial staged bytes and an existing empty/ambiguous state were not reset or initialized. Existing actual native credential/private-store and six real Qt cases passed.

Ledger against claimbase df48d98b8533f84c91506f8f0d7ed38897a92a74 at1c85b0a109d69767c374f793a255e7bc61b32d90 passed21verified, retaining original CI0031 and repair test0036 as then-pending. Public scanner clean, git diff --check exit0. No raw private content was exported. DEF029 is not resolved until all C1-C4 checks and repaired-source native Linux/Windows/full/frozen package gates are reviewed.
