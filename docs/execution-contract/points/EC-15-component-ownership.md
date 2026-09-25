# EC-15 — Component Ownership

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Every substantial component must document what it owns, reads, writes, may decide, may not decide, and what failures it reports.

Avoid overlapping ownership. If two independent components can both decide the same protocol state without explicit arbitration, the design is incomplete.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-15/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-15/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
