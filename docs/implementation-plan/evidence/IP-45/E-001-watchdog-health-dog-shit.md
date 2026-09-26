# IP-45 Evidence — WATCHDOG Health and DOG_SHIT Handling

## Verified capability

WATCHDOG now separates ordinary target/job faults from faults that make the global TB4 control plane unsafe.

- Fault codes are explicitly classified as target-local, transport-recoverable, protocol-blocking, or global-blocking.
- Unknown fault codes are rejected rather than guessed into a severity.
- DOG_SHIT remains one compact current blocking register rather than an append-only error log.
- CLEAN -> BLOCKING and REVIEWED -> BLOCKING/CLEAN use the shared verified StateWalker.
- DOG_SHIT body replacement uses the shared schema-validating, remote-readback BodyKeeper.
- Repeated observation of the same blocker preserves first-seen evidence and increments occurrence_count.
- Normal control work is refused while BLOCKING or REVIEWED.
- Diagnostic reads and bounded repair work remain allowed while blocked.
- REVIEWED is acknowledgement only; CLEAN is permitted only after the underlying invariant is explicitly revalidated.
- WOL failure and one FETCH_BALL_GONE remain nonblocking.
- Health checks use exact object IDs and do not enumerate folders.

## Evidence

- Schema: `protocol/schemas/watchdog-fault.schema.json`
- Implementation: `src/tb4/watchdog/health.py`
- Tests: `tests/watchdog/test_health.py`
- Final implementation commit: `78bdb789bdf3f3892e397eb16032e74eb2fb3f49`
- GitHub Actions run: `36245636978`
- Test job conclusion: **success**
- Full suite: **430 passed**

**Result: VERIFIED.**
