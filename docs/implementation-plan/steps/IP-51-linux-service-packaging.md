# IP-51 - Linux Service Packaging

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Run WATCHDOG or FETCHER as a login-independent Linux service with least privilege and deterministic configuration locations.

## Preconditions

IP-35 through IP-46 VERIFIED.

## Inputs / authoritative references

- `Fetcher/Watchdog service interfaces`
- `Security requirements`

## Work

1. Define CLI entrypoints for watchdog and fetcher.
2. Create systemd unit templates.
3. Define dedicated service user guidance and filesystem permissions.
4. Define environment/config file lookup outside public repo.
5. Handle SIGTERM cleanly and stop child processes.
6. Document install/start/enable/status commands generically.

## Files / modules

- `src/tb4/cli.py`
- `packaging/systemd/tb4-watchdog.service`
- `packaging/systemd/tb4-fetcher.service`
- `docs/INSTALL_LINUX.md`
- `tests/platform/test_linux_service_files.py`

## Required invariants

- Interactive login is not required.
- Secrets are not embedded in unit files committed to repo.

## Tests

- Unit file static validation.
- CLI argument tests.
- Graceful shutdown unit tests.

## Failure cases

- Service requires home-directory interactive shell state.
- Stop leaves RUNNER child alive.

## Completion evidence required

- Packaging tests pass and install docs are reproducible on clean Linux VM/container where feasible.

## Handoff state

Linux pilot hosts can install WATCHDOG/FETCHER services.

## Amendment path

`docs/implementation-plan/amendments/IP-51/`

## Evidence path

`docs/implementation-plan/evidence/IP-51/`
