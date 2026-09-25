# EC-11 — Deterministic Control Path

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Normal runtime should prefer a known stable object identity -> exact read -> exact verified mutation.

Do not use folder enumeration -> name search -> guessing as the normal control path when exact addressing is possible.

Enumeration is appropriate for bootstrap, discovery, audit, repair, migration, and diagnostics.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-11/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-11/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
