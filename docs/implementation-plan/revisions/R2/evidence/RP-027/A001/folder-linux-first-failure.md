# RP-027 A001 actual Linux mapping first failure

Intent RP-027-A001-0139. Exact source `83dd3c09e1446a6897ef0dd64abb6c28fe5d5efb`; trigger `392ca18411ab5e46444b89238debe97b7b0b28c7`.

Both actual native Linux push/PR jobs execute21 cases:20 PASS,1 FAIL,0 SKIP. Required ext4/xfs/native protected C1 and real helper/commissioning tests execute; no fallback to synthetic storage or skipped positive evidence. The failed profile case attempts a changed network scope through actual Setup after BALLPARK publication and raises SETUP_BALLPARK_BINDING_FROZEN before calling mapping preparation. Actual source shows that this is the intended existing immutable binding guard. DEF-075 preserves this fixture error.

Repair the test precondition using actual unchanged-scope Setup write, which advances the protected profile revision; assert the revision changed and retain the actual mapping refusal/no-effect assertions. No production/profile binding guard changes. Original targeted regressions were not run after the failed mapping step. Automatic full CI/Desktop are still running at exact IDs in the JSON report; Progress passed. No C1-C4 acceptance. Next: verified scoped repair and new required native Linux qualification.
