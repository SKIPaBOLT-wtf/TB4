# RP-024 foundation first run

Source: `fd9dad3fb7a07e1f6126dd5c1f53ec0409edb406`. Intent: RP-024-A001-0003.

Windows/Python3.11.9, process-local PYTHONUTF8=1, fresh task-local pytest base.
The five focused files produced **1 failed, 182 passed in 5.80 s**, exit1.
Failed: `tests/drive/test_ballpark_setup.py::test_discovery_change_requires_new_proposal_before_confirmation`.
The test supplied observation time221 while the trusted discovery clock remained220.
`freshness` classifies that observation CLOCK_UNCERTAIN and `Catalogue.observe`
ignores nonfresh observations, so no revision changed. The expected draft conflict
was not actually triggered. This is a test stimulus defect, not evidence that a
real changed discovery revision bypasses confirmation. Preserve the negative case
and repair its stimulus using a later trusted clock, asserting revision advance.
Scanner/diff gates were conditional on test success and did not run.
No shared BALLPARK write or deployment occurred. Remaining publication/UI/native
qualification is still pending; no check is accepted from this run.
