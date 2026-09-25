# EC-39 — Final Rule

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

When uncertain, prefer a smaller deterministic step plus explicit evidence plus canonical repository state over a large clever change plus implicit assumptions plus conversation memory.

The objective is not to make TB4 impressive in one coding session.

The objective is to make TB4 progressively inevitable: every completed step must leave fewer undefined behaviors, fewer assumptions, and fewer things the next agent must rediscover.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-39/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-39/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
