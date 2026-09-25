# EC-04 — Required Project Entrypoints

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Keep project navigation shallow.

The intended reading path is:

`AGENTS.md -> docs/START_HERE.md -> docs/IMPLEMENTATION_PLAN.md -> relevant protocol/config/implementation references`.

`AGENTS.md` must remain short and point to authoritative material instead of duplicating it.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-04/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-04/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
