# IP-58 - Fresh Bootstrap and Reproducibility

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Prove a new installation can be built from public repository documentation and canonical specs without relying on conversation history.

## Preconditions

IP-51, IP-52, IP-57 VERIFIED.

## Inputs / authoritative references

- `Install docs`
- `Bootstrap tool`
- `START_HERE`
- `Configuration docs`

## Work

1. Prepare clean-environment bootstrap checklist for Linux WATCHDOG and Linux/Windows FETCHER.
2. Create sample public-safe configuration templates.
3. Run protocol/tree bootstrap against a fresh test Drive root or test backend.
4. Install services from documented steps on clean environments where available.
5. Run smoke test from READY tree through one synthetic job.
6. Record every undocumented prerequisite discovered and fix docs/scripts.

## Files / modules

- `docs/REPRODUCIBILITY.md`
- `config/examples/`
- `tests/reproducibility/`

## Required invariants

- No hidden conversation-only knowledge required.
- Private deployment values are supplied externally, never embedded in examples.

## Tests

- Fresh package install.
- Fresh tree bootstrap.
- Service startup smoke.
- Synthetic work round-trip.

## Failure cases

- Procedure requires unexplained manual file edits.
- A required artifact exists only in developer machine.

## Completion evidence required

- Clean-environment checklist passes with recorded versions.

## Handoff state

Only environment-specific pilot configuration remains before real deployment.

## Amendment path

`docs/implementation-plan/amendments/IP-58/`

## Evidence path

`docs/implementation-plan/evidence/IP-58/`
