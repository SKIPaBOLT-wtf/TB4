# IP-39 Evidence — WATCHDOG Scheduler

## Verified capability

WATCHDOG now has a deterministic monotonic scheduler for independent helpers.

- Tasks keep independent periodic deadlines.
- DOG_SNOOZE and DOG_AWAKE cadences are supported without changing unrelated schedules.
- Deterministic SHA-256 phase offsets spread devices/tasks across an interval.
- Event-triggered immediate dispatch does not reset the normal periodic deadline.
- Slow callbacks may delay wall-clock dispatch but do not destroy other task timing state.
- Missed intervals are skipped instead of replayed as a catch-up burst.
- Callback exceptions are isolated and recorded in per-task metrics.
- Scheduler exposes bounded wakeup/dispatch/failure metrics.
- No busy-loop mechanism is required; callers can sleep until `next_wakeup_in()`.

## Evidence

- Implementation: `src/tb4/watchdog/scheduler.py`
- Tests: `tests/watchdog/test_scheduler.py`
- Final test commit: `c2b7cdf452c9b6652bffe86b24be7f1bab6a1485`
- GitHub Actions run: `36243377182`
- Test job conclusion: **success**

**Result: VERIFIED.**
