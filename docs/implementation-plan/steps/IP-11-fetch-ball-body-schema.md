# IP-11 - FETCH_BALL Body Schema

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define the exact request and result body for work execution without letting payload or output grow the live control object indefinitely.

## Preconditions

IP-04 VERIFIED and IP-10 VERIFIED.

## Inputs / authoritative references

- `FETCH_BALL state machine`
- `Common control envelope`

## Work

1. Define request payload type, inline payload, and artifact-reference alternatives.
2. Define expected interpreter/runtime hints without embedding private deployment facts.
3. Define result_code, reason_code, exit_code, stdout_tail, stderr_tail, and artifact references.
4. Define fields required in LOADING/TOSS/CHEW/RETURNING/terminal phases.
5. Define PARTIAL evidence fields describing known completed effects.
6. Define GONE semantics with unknown effect marker.
7. Add representative request/result fixtures.

## Files / modules

- `protocol/schemas/fetch-ball.schema.json`
- `protocol/examples/fetch-ball/`
- `tests/protocol/test_fetch_ball_schema.py`

## Required invariants

- Large scripts/results use artifacts.
- A terminal result never erases job_id or generation before COACH consumes it.
- PARTIAL and GONE remain distinguishable.

## Tests

- Inline command request fixture.
- Artifact script request fixture.
- DONE/PARTIAL/FAILED/CANCELLED/GONE result fixtures.
- Oversized inline payload rejected.

## Failure cases

- Schema permits ambiguous payload source.
- PARTIAL lacks evidence fields.
- Terminal body can lose fencing identity.

## Completion evidence required

- All canonical FETCH_BALL fixtures validate and negative fixtures fail.

## Handoff state

Core models and Fetcher pipeline can consume a precise work schema.

## Amendment path

`docs/implementation-plan/amendments/IP-11/`

## Evidence path

`docs/implementation-plan/evidence/IP-11/`
