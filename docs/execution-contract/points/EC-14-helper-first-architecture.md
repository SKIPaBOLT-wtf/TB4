# EC-14 — Helper-First Architecture

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

If an operation is repeated, deterministic, mechanical, or timing-sensitive, implement it as a helper.

Do not repeatedly spend agent reasoning on state verification, retry loops, backoff, hash verification, fencing, deadline arithmetic, retention, tree reconciliation, process cleanup, or result truncation.

The AI/COACH chooses what should happen. Deterministic helpers enforce how it may safely happen.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-14/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-14/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
