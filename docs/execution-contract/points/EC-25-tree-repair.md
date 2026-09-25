# EC-25 — Tree Repair

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

A repair helper must distinguish missing known child, duplicate child, unknown child, corrupt child, and missing root.

A missing safely reconstructable child may be recreated. A duplicate or ambiguous live control object should normally be moved to `DOG_POUND` after preserving the canonical object.

A missing root must never silently create a second independent control plane elsewhere.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-25/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-25/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
