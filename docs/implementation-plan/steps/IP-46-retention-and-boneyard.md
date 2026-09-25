# IP-46 - BONEYARD Retention and Cleanup

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Preserve short-term execution evidence without allowing history or artifacts to grow indefinitely.

## Preconditions

IP-29, IP-33, IP-39 VERIFIED.

## Inputs / authoritative references

- `Retention config`
- `BONEYARD/TOY_BOX tree rules`

## Work

1. Define terminal summary record format for BONEYARD.
2. Define retention timestamp source and grouping strategy.
3. Implement hourly-style sweep using configured interval.
4. Delete only objects proven outside live control path and older than retention.
5. Preserve currently referenced artifacts regardless of nominal age until reference expires.
6. Record cleanup counters without building an append-only log.

## Files / modules

- `src/tb4/watchdog/retention.py`
- `tests/watchdog/test_retention.py`

## Required invariants

- Retention never deletes active control objects.
- Referenced artifacts are not removed prematurely.

## Tests

- Old unreferenced history removed.
- Young history kept.
- Referenced old artifact kept.
- Boundary age.
- Deletion failure isolated.

## Failure cases

- Sweep follows arbitrary remote path outside canonical archive roots.
- Clock anomaly mass-deletes recent evidence.

## Completion evidence required

- Retention tests prove bounded and reference-aware cleanup.

## Handoff state

Long-running WATCHDOG can keep persistent storage bounded.

## Amendment path

`docs/implementation-plan/amendments/IP-46/`

## Evidence path

`docs/implementation-plan/evidence/IP-46/`
