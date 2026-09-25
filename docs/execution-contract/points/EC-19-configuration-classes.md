# EC-19 — Configuration Classes

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Never mix protocol constants, configuration defaults, deployment configuration, runtime state, and historical evidence.

Each configurable parameter must document name, purpose, unit, default, valid range, dependencies, effect of increasing it, effect of decreasing it, runtime reload behavior, and whether per-operation override is allowed.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-19/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-19/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
