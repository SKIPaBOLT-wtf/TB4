# IP-34 Evidence — Result Classifier

## Verified capability

FETCHER now has deterministic classification for trustworthy local execution reports:

- EXITED + exit code 0 -> DONE.
- EXITED + nonzero + no explicit known effects -> FAILED.
- EXITED + nonzero + explicit known effects -> PARTIAL.
- TIMED_OUT + no explicit known effects -> FAILED.
- TIMED_OUT + explicit known effects -> PARTIAL.
- CANCELLED remains CANCELLED while preserving known effects.
- START_FAILED -> FAILED.
- TERMINATION_FAILED is rejected as untrustworthy terminal evidence and must be resolved by later loss/recovery logic.
- stdout/stderr prose is never guessed into side effects.
- GONE is intentionally outside this classifier.

## Evidence

- Implementation: `src/tb4/fetcher/result_judge.py`
- Tests: `tests/fetcher/test_result_judge.py`
- Final test commit: `d0509b6185c267dd2bf791cd9a97b0c8b8e43ca0`
- GitHub Actions run: `36242138595`
- CI conclusion: **success**

**Result: VERIFIED.**
