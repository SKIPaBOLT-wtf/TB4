# IP-38 Evidence — FETCHER Idle and Restart Lifecycle

## Verified capability

FETCHER now has a deterministic restart/idle lifecycle coordinator.

- Idle shutdown is permitted only while FETCH_BALL and STOP_BALL are both READY and no child process or cancellation handling is active.
- The idle interval is configurable through IdleManager rather than hardcoded.
- Any active child or cancellation resets the idle timer instead of merely pausing it.
- Startup uses exact object IDs and performs no folder scan.
- A pending FETCH_BALL_TOSS is surfaced as claimable work for the new instance.
- A pre-existing FETCH_BALL_CHEW is never re-executed by a restarted FETCHER.
- A pre-existing FETCH_BALL_RETURNING is left for recovery rather than fabricated into a result.
- Terminal FETCH_BALL states remain owned by COACH until recycling.
- A non-READY STOP_BALL prevents idle exit/new READY classification.
- An initial DOG_PULSE publication is attempted before normal READY work.

## Evidence

- Implementation: `src/tb4/fetcher/service.py`
- Idle policy: `src/tb4/fetcher/idle_manager.py`
- Tests: `tests/fetcher/test_service_lifecycle.py`
- Final test commit: `43dc6f0999f8078430d2c4bf3e9af29e6d898d70`
- GitHub Actions run: `36243296263`
- CI conclusion: **success**

**Result: VERIFIED.**
