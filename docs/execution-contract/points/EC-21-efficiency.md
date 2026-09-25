# EC-21 — Efficiency

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Design idle behavior as a first-class property.

Prefer event notifications, scheduled timers, exact object reads, cached IDs, write-on-change, bounded backoff, deterministic phase offsets, and local comparison before remote publication.

Avoid busy loops, constant folder scans, rapid unchanged polling, continuous unchanged cloud writes, and AI-driven wait loops.

The idle system should consume negligible CPU and bounded remote operations.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-21/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-21/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
