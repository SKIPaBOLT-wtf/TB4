# RP-025 A001 - first focused collection failure

Source `9c31cf661ace178723792924455c93841e0e1ed1`; test INTENT0005.
Exact already-published source equality was verified, a recoverable local stash
retained that source, and the clean work branch fast-forwarded to checkpoint8d49a50.
A fresh task-owned pytest base was confirmed absent before use.

Actual focused pytest exit2: collection aborted, one ImportError in
tests/drive/test_fetcher_enrollment.py. Its module-level namespace import of
tests.security.test_credential_persistence_native imports the unqualified sibling
test_private_settings_native before the security test directory is on pytest's
import path. Exact error: `ModuleNotFoundError: No module named 'test_private_settings_native'`.
No runtime assertions, scanner or diff gate ran after this failure.

Proven origin is the new test's import composition in source9c31cf6, not runtime
enrollment behavior. Preserve the original failed attempt. Repair only new test
fixture composition with explicit qualified dependencies or self-contained fresh
native fixtures; do not change earlier accepted tests or runtime behavior.
