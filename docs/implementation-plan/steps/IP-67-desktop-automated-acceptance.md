# IP-67 - Desktop Automated Acceptance

> **Status:** Read from `../manifest.yaml`.

## Purpose

Verify desktop source, distribution artifacts and same-host role isolation before live deployment.

## Preconditions

IP-66 VERIFIED.

## Inputs / authoritative references

- `docs/DESKTOP.md`
- All preceding desktop evidence and existing core CI.

## Work

1. Run the full existing Linux suite plus desktop tests on Windows and Linux.
2. Verify packaged applications contain canonical data and resolve both runtime factories.
3. Exercise both app instances, cooperative shutdown and diagnostic privacy.
4. Publish sanitized build/test evidence and checksums without substituting CI for live Drive testing.

## Files / modules

- `.github/workflows/desktop.yml`
- `tests/desktop/`
- `docs/implementation-plan/evidence/IP-67/`

## Required invariants

Exact-commit evidence; no live credentials required; no inferred private-machine success.

## Tests

Exact-commit CI, actual installer/bundle smoke tests and failure-injection coverage.

## Failure cases

Unbuilt installer sources, skipped GUI checks, resource gaps or inconsistent evidence.

## Completion evidence required

Reviewed cross-platform CI and actual build artifact records.

## Handoff state

Public development is verified; inspect the owner's selected workstation before private deployment.

## Amendment path

`docs/implementation-plan/amendments/IP-67/`

## Evidence path

`docs/implementation-plan/evidence/IP-67/`
