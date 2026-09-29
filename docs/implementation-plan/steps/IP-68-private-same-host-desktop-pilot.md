# IP-68 - Private Same-Host Desktop Pilot

> **Status:** Read from `../manifest.yaml`.

## Purpose

Test both separately installed roles on the one workstation explicitly selected by the owner.

## Preconditions

IP-67 VERIFIED; inspect current private workstation, selected root and authorization files.

## Inputs / authoritative references

- `docs/DESKTOP.md`
- `docs/PILOT.md`
- Private owner selection and current-state records outside this repository.

## Work

1. Verify host and mounted-folder visibility without assuming a drive letter from public source.
2. Install each role with rollback; configure one explicit existing root and independent profiles.
3. Test real Drive round trips, script artifacts, cancellation, failures, diagnostics and return to READY.
4. Record disabled wake/bootstrap capabilities honestly; preserve TB3 and unrelated services.

## Files / modules

- `docs/PILOT.md`
- `docs/implementation-plan/evidence/IP-68/`

## Required invariants

Same-host evidence is not independent-machine evidence; no private data in public records; no unknown-effect replay.

## Tests

Actual owner-workstation GUI and Drive round trips, failures and recovery.

## Failure cases

Missing verified access/authorization, failed application startup or uncertain effects.

## Completion evidence required

Sanitized real same-host scenario report tied to exact tested binaries.

## Handoff state

Independent-machine expansion remains a separate later capability check.

## Amendment path

`docs/implementation-plan/amendments/IP-68/`

## Evidence path

`docs/implementation-plan/evidence/IP-68/`
