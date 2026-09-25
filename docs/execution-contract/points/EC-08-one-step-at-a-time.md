# EC-08 — One Step at a Time

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Work in this order: current step -> implement -> test -> verify -> document -> commit -> record completion evidence -> next step.

Do not implement several future plan steps merely because their code appears nearby.

A small prerequisite fix may be included only when it is necessary for the current objective and does not change unrelated architecture. Otherwise amend or add a future plan step.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-08/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-08/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
