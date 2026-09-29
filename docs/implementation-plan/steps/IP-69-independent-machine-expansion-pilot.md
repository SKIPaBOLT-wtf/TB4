# IP-69 - Independent-Machine Expansion Pilot

> **Status:** Read from `../manifest.yaml`.

## Purpose

Retain the independent coordinator/target test after the owner-selected initial same-host pilot.

## Preconditions

IP-68 VERIFIED; independent target selected and accessible.

## Inputs / authoritative references

- `docs/PILOT.md`
- `docs/implementation-plan/steps/IP-60-real-two-machine-pilot.md`
- Private deployment configuration outside this repository.

## Work

1. Repeat the original IP-60 independent-machine scenarios using production helpers.
2. Test applicable wake/bootstrap, GONE/recovery, artifact execution and bounded idle.
3. Keep private topology and credentials outside public evidence.

## Files / modules

- `docs/implementation-plan/evidence/IP-69/`

## Required invariants

Independent physical execution hosts; no manual protocol bypass; no unknown-effect replay.

## Tests

All applicable original independent-machine scenarios, including a real failure recovery.

## Failure cases

Unavailable capability, unverified host access or failed provider semantics.

## Completion evidence required

Sanitized independent-machine scenario report with explicit supported/disabled capabilities.

## Handoff state

Expanded final acceptance can assess both pilot types without conflating them.

## Amendment path

`docs/implementation-plan/amendments/IP-69/`

## Evidence path

`docs/implementation-plan/evidence/IP-69/`
