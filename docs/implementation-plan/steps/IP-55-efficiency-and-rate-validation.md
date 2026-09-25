# IP-55 - Efficiency and Remote-Rate Validation

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Measure idle CPU/timer behavior and remote operation counts to enforce the low-overhead design.

## Preconditions

IP-39 through IP-54 VERIFIED.

## Inputs / authoritative references

- `EC-21`
- `Configuration defaults`

## Work

1. Instrument scheduler wakeups and Drive backend operation counters.
2. Measure idle WATCHDOG loop behavior over accelerated fake time.
3. Verify known-device local probes do not cause unchanged remote writes.
4. Verify normal job path performs no list_children.
5. Verify phase offsets distribute device probes.
6. Define acceptable operation-rate budgets in documentation.
7. Profile obvious hot loops and remove avoidable polling.

## Files / modules

- `tests/performance/test_operation_budget.py`
- `docs/PERFORMANCE.md`

## Required invariants

- Performance changes may not weaken verification/fencing.
- No busy-loop workaround is accepted.

## Tests

- Idle operation budget.
- Unchanged network publication budget.
- No list_children normal path.
- Multi-device phase spread.

## Failure cases

- Optimization removes remote confirmation.
- Metrics themselves cause high write rate.

## Completion evidence required

- Documented operation budgets pass automated tests.

## Handoff state

Security/release work begins from measured bounded behavior.

## Amendment path

`docs/implementation-plan/amendments/IP-55/`

## Evidence path

`docs/implementation-plan/evidence/IP-55/`
