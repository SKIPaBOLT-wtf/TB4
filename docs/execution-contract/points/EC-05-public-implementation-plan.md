# EC-05 — Public Implementation Plan

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Maintain `docs/IMPLEMENTATION_PLAN.md` as the public chronological source of project progress.

The plan is an executable development sequence, not a wish list. Every numbered step must depend only on earlier completed steps plus explicitly existing repository state.

A later step must never silently depend on work planned even later.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-05/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-05/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
