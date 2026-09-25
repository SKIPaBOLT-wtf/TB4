# EC-31 — Git Discipline

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Commits should describe one coherent change. Prefer messages such as “Add generation fence validator” or “Implement verified Drive rename helper.”

Avoid vague commits such as “Fix TB4” or “Update stuff.”

Do not combine unrelated cleanup with protocol behavior changes.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-31/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-31/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
