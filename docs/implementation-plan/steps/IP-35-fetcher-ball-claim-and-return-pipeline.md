# IP-35 - FETCHER Ball Claim and Return Pipeline

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement the core FETCHER lifecycle from TOSS claim through CHEW execution and verified terminal return.

## Preconditions

IP-24, IP-25, IP-30 through IP-34 VERIFIED.

## Inputs / authoritative references

- `FETCH_BALL state machine/schema`
- `StateWalker`
- `BodyKeeper`
- `FenceGuard`

## Work

1. Observe exact FETCH_BALL object ID rather than scanning PLAYGROUND.
2. On TOSS validate body schema, expiry, job_id, and generation.
3. Claim TOSS -> CHEW through StateWalker.
4. Write started_at only after CHEW is remotely confirmed.
5. Execute inline or artifact request through RUNNER.
6. Transition CHEW -> RETURNING before writing terminal result body.
7. Write/verify result body.
8. Transition RETURNING -> DONE/PARTIAL/FAILED/CANCELLED as classified.
9. Reject stale worker at every dependent write through FenceGuard.

## Files / modules

- `src/tb4/fetcher/ball_pipeline.py`
- `tests/fetcher/test_ball_pipeline.py`

## Required invariants

- Rename/state confirmation always precedes dependent body writes.
- One stale Fetcher cannot overwrite newer generation.
- Fetcher never lists PLAYGROUND on normal path.

## Tests

- DONE flow.
- PARTIAL flow.
- FAILED flow.
- Expired TOSS.
- Stale generation during execution.
- Delayed Drive rename/body visibility.

## Failure cases

- Execution starts before claim remotely confirmed.
- Terminal state published before result body readback verifies.

## Completion evidence required

- End-to-end pipeline tests pass against InMemoryDriveBackend with injected delays.

## Handoff state

Remaining FETCHER lifecycle features can wrap a working single-job pipeline.

## Amendment path

`docs/implementation-plan/amendments/IP-35/`

## Evidence path

`docs/implementation-plan/evidence/IP-35/`
