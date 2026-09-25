# EC-28 — Failure Injection

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Recovery code is not considered validated merely because it looks correct.

Deliberately force failures such as worker termination during execution, delayed storage visibility, ambiguous write result, service restart during active operation, corrupt object body, duplicate control object, stale generation, disconnected transport, clock error, and oversized output.

Verify deterministic recovery.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-28/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-28/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
