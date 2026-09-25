# EC-27 — Testing Rule

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Testing belongs inside every plan step rather than at the end.

As applicable, cover happy path, idempotent repeat, wrong expected state, malformed input, delayed visibility, retry exhaustion, stale generation, duplicate operation, process interruption, timeout, cancellation, partial execution, unknown result, and restart recovery.

Not every step needs every case, but every relevant failure mode must eventually have an explicit test owner in the plan.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-27/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-27/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
