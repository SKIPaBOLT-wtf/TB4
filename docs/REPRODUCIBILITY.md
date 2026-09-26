# Fresh Bootstrap and Reproducibility

This checklist proves that a new TB4 checkout can be understood, installed, bootstrapped, and smoke-tested without conversation history or private deployment knowledge.

## 1. Public prerequisites

- Python 3.11 or newer.
- A fresh checkout of this repository.
- No private credentials are needed for the in-memory reproducibility path.
- Google Drive credentials are required only for a real deployment and are configured separately as described in `GOOGLE_DRIVE_SETUP.md`.

## 2. Fresh Python environment

From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Windows PowerShell uses the environment activation command appropriate for the local Python installation.

Then run:

```sh
python tools/scan_public_repo.py
pytest
```

Both must succeed before deployment preparation.

## 3. Zero-knowledge protocol bootstrap

The deterministic in-memory backend contains one existing root folder. No hidden root ID is required:

```sh
python tools/bootstrap_drive.py --demo-memory
```

Expected properties:

- exit code 0;
- a JSON report is printed;
- `root_id` identifies the in-memory root;
- canonical static children are created from `protocol/tree-blueprint.yaml`;
- `PARK_MAP` is written and verified;
- no private host identity is invented.

The core `bootstrap_tree()` contract remains stricter than this demo convenience: real backends require an explicitly selected existing root and never create a second TB4 root automatically.

## 4. Public-safe configuration templates

Copy, do not edit in place:

```text
config/examples/watchdog.toml.example
config/examples/fetcher.toml.example
```

Deployment-specific values must be supplied outside the public repository. The examples use obvious non-secret placeholders and documentation-only example identities.

## 5. Service-boundary checks

Linux examples:

```sh
tb4 watchdog --check --config /etc/tb4/watchdog.toml
tb4 fetcher --check --config /etc/tb4/fetcher.toml
```

These checks validate the service/config boundary only. They do not claim that a real Drive account, WOL path, SSH path, or target runtime is already configured.

Platform service installation is documented in:

- `INSTALL_LINUX.md`
- `INSTALL_WINDOWS.md`

## 6. Synthetic round trip

The reproducibility test suite constructs a fresh deterministic backend, bootstraps the canonical tree, registers a synthetic target, tosses one job, returns a successful result, and recycles the ball to `FETCH_BALL_READY`.

Run:

```sh
pytest tests/reproducibility -q
```

This proves the public repository contains enough information and code for a clean synthetic control-plane round trip.

## 7. What this step deliberately does not prove

Fresh reproducibility is not the private pilot.

It does not prove:

- access to a real private Drive root;
- real OAuth authorization;
- real Wake-on-LAN;
- real SSH bootstrap;
- Linux/Windows service behavior on the user's actual machines;
- real cross-machine execution.

Those belong to IP-59 and IP-60.

## 8. Reproducibility pass criteria

IP-58 may be considered complete when all of the following are true:

1. CI installs the package from the public repository and passes.
2. The public security scan passes.
3. `python tools/bootstrap_drive.py --demo-memory` succeeds without hidden object IDs.
4. Public-safe WATCHDOG and FETCHER example configs parse as TOML.
5. The reproducibility smoke test reaches `FETCH_BALL_DONE` and recycles to `FETCH_BALL_READY`.
6. No step depends on conversation-only deployment facts.
