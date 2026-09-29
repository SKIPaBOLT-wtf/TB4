# IP-62 - Desktop Role Contract

> **Status:** Read from `../manifest.yaml`.

## Purpose

Specify separate applications, same-host isolation, safe configuration and development-before-pilot acceptance.

## Preconditions

IP-59 VERIFIED; owner scope amendment accepted.

## Inputs / authoritative references

- `docs/DESKTOP.md`
- `docs/implementation-plan/amendments/IP-60/A-001-desktop-development-first.md`

## Work

1. Define role-specific applications, profiles, controls, installers and uninstall behavior.
2. Preserve canonical API transactions; a mounted folder is not remote confirmation.
3. Separate automated development evidence, same-host pilot and independent-machine pilot.

## Files / modules

- `docs/DESKTOP.md`
- `tests/desktop/test_plan.py`

## Required invariants

No private deployment identifiers. Preserve IP-01..IP-59 and historical pilot records. No protocol changes.

## Tests

Plan structure and references; historical status preservation; explicit non-goals.

## Failure cases

Conflicting scope, mixed evidence, missing dependencies or implicit identity reuse.

## Completion evidence required

Structural tests, baseline comparison and reviewed desktop contract.

## Handoff state

Implement local desktop support without requiring private deployment credentials.

## Amendment path

`docs/implementation-plan/amendments/IP-62/`

## Evidence path

`docs/implementation-plan/evidence/IP-62/`
