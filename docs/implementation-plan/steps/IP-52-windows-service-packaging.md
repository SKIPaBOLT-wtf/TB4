# IP-52 - Windows Service Packaging

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Run FETCHER as a login-independent Windows service with the same protocol and safe process-tree behavior.

## Preconditions

IP-35 through IP-38 VERIFIED.

## Inputs / authoritative references

- `Fetcher service interface`
- `Security requirements`

## Work

1. Choose a reproducible Windows service wrapper/implementation approach.
2. Add service install/uninstall/start/status tooling.
3. Define private config path and least-privilege service account guidance.
4. Implement child process-tree termination compatible with Windows.
5. Ensure PowerShell/script artifact execution does not require interactive profile.
6. Document generic setup.

## Files / modules

- `packaging/windows/`
- `src/tb4/platform/windows_service.py`
- `docs/INSTALL_WINDOWS.md`
- `tests/platform/test_windows_service_config.py`

## Required invariants

- Protocol behavior remains identical across OSes.
- No private credentials embedded in service definition.

## Tests

- Service command generation.
- Path quoting.
- PowerShell script artifact execution contract.
- Termination behavior mocked/tested.

## Failure cases

- Execution depends on logged-in desktop session.
- Windows quoting recreates giant inline-script problem.

## Completion evidence required

- Windows packaging tests pass and manual clean-host checklist exists.

## Handoff state

Windows target pilot can run FETCHER before user login.

## Amendment path

`docs/implementation-plan/amendments/IP-52/`

## Evidence path

`docs/implementation-plan/evidence/IP-52/`
