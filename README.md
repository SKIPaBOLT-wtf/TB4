# TB4

TB4 is an experimental terminal-bridge project for deterministic, low-overhead remote development and debugging workflows.

The repository is the project's persistent public memory. Private deployment details, credentials, and private infrastructure information do not belong here.

## Desktop applications

WATCHDOG and FETCHER have separate Windows installers and Linux desktop bundles,
each with its own system-tray application for configuration, status and diagnostics.
Start with the [desktop quick start](docs/DESKTOP_QUICKSTART.md). The
[desktop contract](docs/DESKTOP.md) defines isolation, safety and rollback.

Build and installer evidence is under implementation-plan steps IP-64 through
IP-67. The first private same-host pilot is IP-68; an independent-machine pilot
remains a separate later step. Only the [manifest](docs/implementation-plan/manifest.yaml)
contains authoritative completion status. A successful build is not a live pilot.

## Development reference

The project's development method is defined by the [TB4 Execution Contract](docs/execution-contract/README.md).

The execution contract and the implementation plan are deliberately separate:

- **Execution Contract:** how development must be performed and verified.
- **Implementation Plan:** concrete chronological engineering work.

## Vocabulary

TB4 intentionally keeps its dog/ball language. Names such as `DOG_HOUSE`, `BALL_PARK`, `KENNEL`, `FETCH_BALL`, `WAKE_BONE`, `DOG_SNOOZE`, `DOG_SHIT`, `BONEYARD`, and `DOG_POUND` are project terminology.

Humor is allowed. Ambiguity is not.
