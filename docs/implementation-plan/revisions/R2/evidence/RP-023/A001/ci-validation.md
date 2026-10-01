# RP023 Linux CI and progress evidence

Runtime/test/workflow source: `a423b69e03bd43c756cfb1077a5920fed93b42de`. Trigger: `f975511e8d7c4eafeba51d570c1d391e229a9aa9`. Actual logged checkout: `c2fe144624487711a3efcbb874213d3c59efcf7c` (PR32 merge against main1abf3d6). Exact Git comparison of src/tests/workflows/tools/protocol/config/packaging/pyproject between source and checkout returned0. Later documentation-only heads do not change this evidence scope.

CI run36838966326/job110293145041 completed SUCCESS. Python3.11.16; full suite2124 passed,20 skipped,4 strict historical expected failures in616.64s. Native Linux credential gate33 passed0.16s; protected first-run34 passed0.65s; mandatory isolated loopback discovery2 passed0.04s with TB4_REQUIRE_NATIVE_DISCOVERY=1. Full test step explicitly required isolated folder SSH (TB4_REQUIRE_FOLDER_SSH=1); public scanner clean. The complete run does not qualify a home/routed deployment.

Progress run36838966397/job110293145097 completed SUCCESS on the same checkout:196 passed5.27s; current ledger and main-base append-only history both PASS,22 VERIFIED, sole pending RP-023-A001-0038; scanner clean. Historical failed attempts and open revalidation holds were accepted structurally, not erased.

Windows/Linux Desktop full tests, frozen applications, installer acceptance and artifact metadata are still pending at this checkpoint. RP023 is not yet accepted.
