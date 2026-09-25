# IP-04 - FETCH_BALL State Machine

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define the complete work-channel lifecycle before execution code exists.

## Preconditions

IP-03 VERIFIED.

## Inputs / authoritative references

- `protocol/objects.yaml`
- `EC-12`
- `EC-16`
- `EC-23`

## Work

1. Define READY -> LOADING -> TOSS -> CHEW -> RETURNING lifecycle.
2. Define terminal states DONE, PARTIAL, FAILED, CANCELLED, and GONE.
3. Define RECYCLING -> READY reset flow.
4. Assign the component allowed to initiate every transition.
5. Define which states allow body mutation.
6. Define mutating GONE rule: inspect effects before replay.
7. Define idempotent target-state repeat and illegal transitions.

## Files / modules

- `protocol/state-machines.yaml`
- `docs/FETCH_BALL.md`
- `tests/protocol/test_fetch_ball_spec.py`

## Required invariants

- One logical FETCH_BALL is used per target work thread in protocol v1.
- Object name is authoritative state; body holds job identity and evidence.
- GONE never implies safe replay.

## Tests

- Every legal transition is accepted.
- Representative illegal transitions are rejected.
- Every state has an owner and terminal/nonterminal classification.

## Failure cases

- A state has no legal recovery path.
- Two components may independently claim the same transition without arbitration.

## Completion evidence required

- Machine-readable FETCH_BALL graph validates.
- Transition coverage tests pass.

## Handoff state

Schemas and validators may rely on a frozen work-channel lifecycle.

## Amendment path

`docs/implementation-plan/amendments/IP-04/`

## Evidence path

`docs/implementation-plan/evidence/IP-04/`
