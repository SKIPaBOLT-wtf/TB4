# EC-32 — Step Completion Loop

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

At the end of every implementation step: run relevant tests -> inspect actual diff -> verify required invariants -> update documentation if behavior changed -> record completion evidence -> update `IMPLEMENTATION_PLAN.md` -> commit -> confirm repository is clean.

Never mark a step complete before this sequence succeeds.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-32/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-32/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
