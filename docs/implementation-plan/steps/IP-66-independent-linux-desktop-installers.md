# IP-66 - Independent Linux Desktop Installers

> **Status:** Read from `../manifest.yaml`.

## Purpose

Build separate Linux desktop distributions and per-user installation/uninstallation paths.

## Preconditions

IP-65 VERIFIED.

## Inputs / authoritative references

- `docs/DESKTOP.md`
- Existing Linux packaging and desktop entrypoints.

## Work

1. Bundle separate role applications with Qt and runtime data.
2. Install role-scoped launchers and desktop entries without modifying existing services.
3. Preserve profiles, the peer role and rollback binaries.
4. Smoke-test installation and removal in an isolated home directory.

## Files / modules

- `packaging/desktop/`
- `tools/build_desktop.py`
- `.github/workflows/desktop.yml`
- `tests/desktop/`

## Required invariants

No root privileges or existing-service mutation; private state preserved; no source checkout needed.

## Tests

Linux bundle self-test, isolated install/uninstall, path quoting, role isolation and no-tray fallback.

## Failure cases

Missing shared libraries, unsafe paths, active-role replacement and incorrect desktop integration.

## Completion evidence required

Actual Linux build/install/uninstall outcomes and artifact checksums.

## Handoff state

Both platform distributions can enter automated desktop acceptance.

## Amendment path

`docs/implementation-plan/amendments/IP-66/`

## Evidence path

`docs/implementation-plan/evidence/IP-66/`
