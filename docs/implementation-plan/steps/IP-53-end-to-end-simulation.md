# IP-53 - End-to-End In-Memory Simulation

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Exercise COACH-like dispatch, WATCHDOG, FETCHER, RUNNER, and Drive transactions together without real LAN or Google dependencies.

## Preconditions

IP-35 through IP-46 VERIFIED.

## Inputs / authoritative references

- `All canonical state machines and helper contracts`

## Work

1. Build simulation harness with InMemoryDriveBackend, fake network probe, fake WOL/SSH, fake Runner, and fake clock.
2. Bootstrap canonical tree.
3. Simulate target asleep -> WAKE_BONE_TOSS -> WATCHDOG wake -> fresh pulse.
4. Dispatch FETCH_BALL_TOSS -> CHEW -> terminal result -> consume -> READY.
5. Run two independent target trees concurrently to prove one thread per device rather than one global LAN thread.
6. Assert exact object operation counts.

## Files / modules

- `tests/integration/test_end_to_end_simulation.py`
- `tests/support/simulation.py`

## Required invariants

- Simulation uses production orchestration/helpers where possible, not a parallel fake protocol.
- Each target state is independent.

## Tests

- Awake target direct job.
- Sleeping target wake then job.
- Two target concurrent jobs.
- Partial result.
- Cancel.
- Target loss.

## Failure cases

- Global single BALL blocks unrelated target.
- Simulation bypasses verified transaction helpers.

## Completion evidence required

- End-to-end simulated flows pass with deterministic fake clock.

## Handoff state

Failure injection can now target integrated behavior.

## Amendment path

`docs/implementation-plan/amendments/IP-53/`

## Evidence path

`docs/implementation-plan/evidence/IP-53/`
