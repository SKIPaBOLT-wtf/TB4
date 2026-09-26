# IP-36 Evidence — FETCHER Heartbeat

## Verified capability

FETCHER now publishes bounded liveness evidence through one exact DOG_PULSE object ID.

- Local monotonic time controls due cadence.
- UTC Unix epoch time is protocol evidence only.
- Active cadence is more responsive than idle cadence.
- Sequence advances only after remotely confirmed publication.
- A failed remote write still consumes the local cadence window, preventing a tight caller loop from hammering Drive.
- Claimed generation and operation ID are published only as a matched pair.
- Backward wall-clock movement is rejected without a remote write.
- Delayed remote visibility is reconciled through bounded confirmation reads without replaying the write.
- No folder scan is used.

## Evidence

- Implementation: `src/tb4/fetcher/heartbeat.py`
- Tests: `tests/fetcher/test_heartbeat.py`
- Final test commit: `388a46f025ba3faee4485929d61ee6c12f1f7bd1`
- GitHub Actions run: `36242379180`
- CI conclusion: **success**

**Result: VERIFIED.**
