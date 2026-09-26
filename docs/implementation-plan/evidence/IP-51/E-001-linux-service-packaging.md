# IP-51 Evidence E-001 — Linux service packaging

## Verified capability

Linux service packaging boundary is implemented for WATCHDOG and FETCHER.

## Evidence

- `tb4` console entrypoint is installed from `pyproject.toml`.
- Deterministic external config paths are `/etc/tb4/watchdog.toml` and `/etc/tb4/fetcher.toml`.
- systemd templates run under dedicated `tb4` user/group and contain no embedded credentials.
- `ServiceHost` converts SIGTERM/SIGINT into a shared stop event and runs cleanup callbacks exactly once in reverse order.
- Linux packaging tests cover service-file invariants, CLI defaults, and shutdown cleanup behavior.
- GitHub Actions run 36268756043 completed the test command successfully on Ubuntu 24.04 / Python 3.11.
- Full suite result: **486 passed in 8.33s**.

Workflow: https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36268756043

## Boundary clarification

Per amendment A-001, this verifies the Linux packaging/service wrapper. Full runtime composition and real pilot readiness remain owned by later integration and pilot steps.
