# IP-65 - Independent Windows Desktop Installers

> **Status:** Read from `../manifest.yaml`.

## Purpose

Build separate self-contained Windows installers for the two desktop roles.

## Preconditions

IP-64 VERIFIED.

## Inputs / authoritative references

- `docs/DESKTOP.md`
- Existing Windows packaging and desktop entrypoints.

## Work

1. Bundle executables, GUI/runtime dependencies and canonical protocol/default data.
2. Create separate non-admin installers, launchers, logon entries and uninstall identities.
3. Refuse unsafe replacement while running and preserve private profiles and the peer role.
4. Compile and smoke-test actual installers in Windows CI.

## Files / modules

- `packaging/desktop/`
- `tools/build_desktop.py`
- `.github/workflows/desktop.yml`
- `tests/desktop/`

## Required invariants

No source checkout or preinstalled Python required; no automatic work before setup; no service or peer-role replacement.

## Tests

Packaged self-test; two-role silent install/uninstall isolation; unconfigured installation does not start work.

## Failure cases

Missing bundled dependencies, installer compile errors, in-use upgrade, uninstall crossing role boundaries.

## Completion evidence required

Actual Windows build and installer smoke-test outcomes, exact commit and artifact checksums.

## Handoff state

Windows distribution is verified independently of private workstation deployment.

## Amendment path

`docs/implementation-plan/amendments/IP-65/`

## Evidence path

`docs/implementation-plan/evidence/IP-65/`
