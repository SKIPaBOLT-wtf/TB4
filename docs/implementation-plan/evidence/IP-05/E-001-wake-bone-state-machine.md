# IP-05 Evidence - WAKE_BONE State Machine

Date: 2026-09-25

## Verified

- Canonical lifecycle is defined: READY, LOADING, TOSS, CHEW, DONE, FAILED, RECYCLING.
- WATCHDOG owns the request after TOSS.
- Expired requests are terminalized without WOL/SSH action.
- Success requires a fresh target DOG_PULSE rather than only ping/SSH success.
- Wake/bootstrap failures remain target-local.
- GitHub Actions CI run `36194223011` completed successfully for commit `3127d17d6bef5c405ea0141f5bfb817b95ef0d7c`.
- The CI `Test` step completed successfully.

## Result

IP-05 completion criteria are satisfied.
