# IP-18 - State Transition Validator

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement pure deterministic validation of state transitions from the machine-readable state-machine specification.

## Preconditions

IP-16 and IP-17 VERIFIED.

## Inputs / authoritative references

- `protocol/state-machines.yaml`

## Work

1. Load canonical transition tables once.
2. Expose validate_transition(object_root,current,target,actor).
3. Return explicit legal, idempotent, or illegal result.
4. Validate transition actor ownership.
5. Support terminal-state classification queries.
6. Keep function free of Drive/network side effects.

## Files / modules

- `src/tb4/core/state_machine.py`
- `tests/core/test_state_machine.py`

## Required invariants

- No transition exists only in code.
- Idempotent target-state check is distinguishable from a new legal transition.

## Tests

- Exhaustive legal transitions.
- Illegal cross-object states.
- Wrong actor rejected.
- Idempotent same-state behavior.

## Failure cases

- Runtime code can bypass transition table using raw strings.

## Completion evidence required

- Exhaustive tests cover every canonical transition edge.

## Handoff state

StateWalker may rely on a pure validator before mutating remote objects.

## Amendment path

`docs/implementation-plan/amendments/IP-18/`

## Evidence path

`docs/implementation-plan/evidence/IP-18/`
