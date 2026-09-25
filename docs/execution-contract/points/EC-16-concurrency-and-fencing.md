# EC-16 — Concurrency and Fencing

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Assume old processes can wake, remote visibility can be delayed, machines can reboot, workers can crash, jobs can be replaced, and duplicate execution attempts can occur.

Reusable execution channels therefore require fencing. A state-changing operation may need to validate stable object identity, expected state, operation ID, and generation.

A stale participant must detect that it no longer owns the operation and stop without modifying the current generation. This behavior requires explicit tests.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-16/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-16/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
