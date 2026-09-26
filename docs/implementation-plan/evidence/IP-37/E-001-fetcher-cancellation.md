# IP-37 Evidence — FETCHER Cancellation

## Verified capability

FETCHER now handles STOP_BALL as a generation-safe, exact-object cancellation channel.

- RUNNER may call the cancellation callback frequently, but Drive reads are bounded by a monotonic poll gate.
- A cancellation request must match exact FETCH_BALL object ID, job ID, and generation.
- Only FETCH_BALL_CHEW is actively cancellable.
- A request for an already terminal job is durably acknowledged as `ALREADY_TERMINAL` without signalling process termination.
- A stale/mismatched generation is durably acknowledged as `NO_MATCH` and cannot cancel the current job.
- A matching request is claimed REQUESTED -> RETURNING, acknowledgement body is remotely verified, then ACKNOWLEDGED is published.
- Repeated callback calls after a successful cancellation are locally latched and do not repeat Drive writes.
- POSIX forced-kill behavior is tested when the child ignores SIGTERM.
- STOP_BALL remains ACKNOWLEDGED for COACH to consume; FETCHER does not prematurely recycle it.

## Evidence

- Implementation: `src/tb4/fetcher/cancellation.py`
- Tests: `tests/fetcher/test_cancellation.py`
- Final test commit: `af5ad39fb988156710582c291626c83496ce08f9`
- GitHub Actions run: `36242507419`
- CI conclusion: **success**

**Result: VERIFIED.**
