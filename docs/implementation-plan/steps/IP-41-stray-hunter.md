# IP-41 - STRAY_HUNTER Discovery

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Discover previously unknown LAN devices on a slower independent schedule without polluting active control paths.

## Preconditions

IP-39 and IP-40 VERIFIED.

## Inputs / authoritative references

- `STRAY_YARD tree blueprint`
- `Network discovery timing`

## Work

1. Define discovery backend interface separate from known-device probe.
2. Normalize discovered device identity using stable hardware identifier when available.
3. Create deterministic generic stray key without private names.
4. Update STRAY_YARD only for new/changed discoveries.
5. Never auto-promote a stray into BALL_PARK target capabilities.
6. Record bounded first_seen/last_seen evidence.

## Files / modules

- `src/tb4/watchdog/stray_hunter.py`
- `tests/watchdog/test_stray_hunter.py`

## Required invariants

- Discovery is maintenance/observation, not execution authorization.
- Full scan cadence remains much slower than known-device probe.

## Tests

- New device.
- Repeated unchanged device.
- Address change same stable identity.
- Identity unavailable.
- Discovery backend failure.

## Failure cases

- Unknown device automatically becomes executable target.
- Scan floods Drive with unchanged observations.

## Completion evidence required

- Discovery tests prove deterministic deduplication and bounded writes.

## Handoff state

WATCHDOG can report LAN newcomers independently from work dispatch.

## Amendment path

`docs/implementation-plan/amendments/IP-41/`

## Evidence path

`docs/implementation-plan/evidence/IP-41/`
