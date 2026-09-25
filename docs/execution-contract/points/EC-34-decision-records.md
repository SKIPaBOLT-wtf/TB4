# EC-34 — Decision Records

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Preserve non-obvious architectural choices using lightweight decision records.

A decision record should contain problem, decision, reason, alternatives rejected, compatibility impact, and date.

Do not create decision records for trivial implementation details.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-34/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-34/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
