# IP-08 - Device Observation and Local Fault Semantics

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define per-device identity, freshness, executor heartbeat, LAN observation, and target-local infrastructure failures.

## Preconditions

IP-03 VERIFIED and IP-07 VERIFIED.

## Inputs / authoritative references

- `EC-22`
- `WATCHDOG control state rules`

## Work

1. Define DOG_TAG identity and capability fields.
2. Define DOG_PULSE as target executor heartbeat.
3. Define DOG_SNIFF as WATCHDOG LAN observation.
4. Define a target-local fault object/state that does not reuse DOG_SHIT.
5. Define fresh, stale, offline, and unknown semantics with timestamps.
6. Define precedence when pulse and sniff observations disagree.
7. Define which observation fields trigger remote publication versus local-only state.

## Files / modules

- `protocol/objects.yaml`
- `docs/DEVICE_STATE.md`
- `tests/protocol/test_device_state_spec.py`

## Required invariants

- One target may be unavailable without blocking the whole BALL_PARK.
- Absence is not silently equivalent to offline until freshness rules permit that conclusion.

## Tests

- Required identity/capability fields validated.
- Fresh/stale boundaries covered.
- Conflicting pulse/sniff examples resolve deterministically.

## Failure cases

- Conflicting observations have no resolution rule.
- Target-local fault accidentally escalates to DOG_SHIT.

## Completion evidence required

- Device observation specification covers normal and conflicting observations.

## Handoff state

The tree blueprint and status schemas can include stable per-device objects.

## Amendment path

`docs/implementation-plan/amendments/IP-08/`

## Evidence path

`docs/implementation-plan/evidence/IP-08/`
