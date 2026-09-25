# IP-59 - Private Pilot Preparation

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Prepare a safe deployment checklist and private configuration boundary for the first real coordinator and target without committing private details.

## Preconditions

IP-58 VERIFIED.

## Inputs / authoritative references

- `Security docs`
- `Install docs`
- `Configuration reference`

## Work

1. Define private deployment config template for one WATCHDOG and one target.
2. List required capabilities: Drive auth, target identity, WOL data if applicable, SSH bootstrap reference if applicable.
3. Validate timing defaults against expected small-LAN behavior.
4. Create preflight commands that report readiness without exposing secrets.
5. Create rollback/uninstall checklist.
6. Ensure public evidence records only generic pass/fail facts.

## Files / modules

- `docs/PILOT.md`
- `config/examples/pilot.example.toml`
- `tools/preflight.py`

## Required invariants

- Actual private values remain outside repository.
- Pilot does not bypass protocol because environment is trusted.

## Tests

- Example config validates.
- Preflight with missing capability gives precise result.
- Rollback paths documented.

## Failure cases

- Pilot requires code edits for private host values.
- Secrets needed in GitHub.

## Completion evidence required

- Generic pilot checklist and validation tooling are ready.

## Handoff state

User/environment intervention may now provide private configuration and host access for IP-60.

## Amendment path

`docs/implementation-plan/amendments/IP-59/`

## Evidence path

`docs/implementation-plan/evidence/IP-59/`
