# IP-13 - DOG_TAG, DOG_PULSE, DOG_SNIFF, and Fault Schemas

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define exact compact schemas for device identity, executor heartbeat, LAN observation, and target-local fault reporting.

## Preconditions

IP-08 and IP-10 VERIFIED.

## Inputs / authoritative references

- `Device observation semantics`
- `Canonical tree`

## Work

1. Define DOG_TAG stable identity and capability fields.
2. Define DOG_PULSE timestamp/sequence/generation ownership fields.
3. Define DOG_SNIFF last observation, observed address metadata, and freshness fields.
4. Define target-local fault record fields and severity.
5. Define bounded human-readable description fields.
6. Create examples for online, stale, offline, and unknown devices.

## Files / modules

- `protocol/schemas/dog-tag.schema.json`
- `protocol/schemas/dog-pulse.schema.json`
- `protocol/schemas/dog-sniff.schema.json`
- `protocol/schemas/target-fault.schema.json`
- `tests/protocol/test_status_schemas.py`

## Required invariants

- Capabilities describe what may be attempted, not current reachability.
- Heartbeat and LAN observation are separate evidence sources.

## Tests

- All example states validate.
- Invalid sequence/time types rejected.
- Secret-like fields are absent from schemas.

## Failure cases

- Schema conflates capability with online state.
- Observation can grow unbounded.

## Completion evidence required

- Status/identity schema tests pass.

## Handoff state

Watchdog and Fetcher can exchange bounded status objects.

## Amendment path

`docs/implementation-plan/amendments/IP-13/`

## Evidence path

`docs/implementation-plan/evidence/IP-13/`
