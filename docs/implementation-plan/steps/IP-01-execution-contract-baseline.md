# IP-01 - Execution Contract Baseline

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Persist the development contract that governs every later TB4 change.

## Preconditions

None.

## Inputs / authoritative references

- `docs/execution-contract/`

## Work

1. Keep EC-01 through EC-39 as the canonical development contract.
2. Keep contract status, amendments, and evidence isolated from implementation-plan status.
3. Ensure repository navigation points future agents to the contract before implementation work.

## Files / modules

- `docs/execution-contract/`
- `AGENTS.md`
- `docs/START_HERE.md`

## Required invariants

- Do not mix execution-contract status with implementation-step status.

## Tests

- Count 39 canonical contract point files and 39 manifest entries.
- Confirm amendment and evidence directories exist.

## Failure cases

- Missing or duplicated EC point blocks later planning.

## Completion evidence required

- 39 contract point files exist.
- 39 execution-contract manifest entries exist.
- Navigation points to the execution contract.

## Handoff state

Future steps may rely on the execution contract as project methodology.

## Amendment path

`docs/implementation-plan/amendments/IP-01/`

## Evidence path

`docs/implementation-plan/evidence/IP-01/`
