# IP-05 - WAKE_BONE State Machine

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define deterministic target wake and bootstrap control independently of FETCH_BALL.

## Preconditions

IP-03 VERIFIED.

## Inputs / authoritative references

- `protocol/objects.yaml`
- `EC-12`

## Work

1. Define READY -> LOADING -> TOSS -> CHEW flow.
2. Define DONE and FAILED terminal outcomes.
3. Define RECYCLING -> READY.
4. Assign WATCHDOG ownership after TOSS.
5. Define request expiry and stale request behavior.
6. Keep ordinary wake failure separate from DOG_SHIT blocking faults.

## Files / modules

- `protocol/state-machines.yaml`
- `docs/WAKE_BONE.md`
- `tests/protocol/test_wake_bone_spec.py`

## Required invariants

- Wake failure is target-local unless control-plane integrity is compromised.
- Expired wake requests must not execute.

## Tests

- Legal and illegal transitions are covered.
- Expiry is represented.
- WAKE_BONE cannot directly create FETCH_BALL execution.

## Failure cases

- Wake state can become permanently ownerless.
- Ordinary wake failure escalates globally without protocol reason.

## Completion evidence required

- WAKE_BONE graph and ownership rules validate.

## Handoff state

WATCHDOG wake implementation can later follow one canonical lifecycle.

## Amendment path

`docs/implementation-plan/amendments/IP-05/`

## Evidence path

`docs/implementation-plan/evidence/IP-05/`
