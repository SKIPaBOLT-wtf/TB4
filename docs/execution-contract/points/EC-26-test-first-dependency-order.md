# EC-26 — Test-First Dependency Order

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Prefer this progression: protocol vocabulary -> machine-readable state definitions -> schemas -> pure validators -> state-transition helpers -> fencing -> retry/timing helpers -> storage backend primitives -> storage transaction layer -> runtime services -> execution runner -> failure recovery -> platform service integration -> multi-component integration -> real pilot -> hardening -> release.

Do not implement high-level automation while lower-level safety contracts remain undefined.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-26/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-26/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
