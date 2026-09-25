# EC-33 — Completion Evidence

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Use measurable completion evidence.

Good evidence: exact test counts, explicit rejected illegal transitions, proof that stale generations cannot overwrite current state, or proof that normal-path helpers do not enumerate folders.

“Looks good,” “should work,” and “implementation complete” are not acceptable evidence.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-33/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-33/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
