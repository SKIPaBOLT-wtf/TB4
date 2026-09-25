# EC-30 — Protocol Changes

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

If implementation reveals a protocol design error, do not hide it as a local coding fix.

Identify the problem -> determine compatibility impact -> update canonical specification -> update machine-readable contract -> update tests -> update implementation -> update documentation -> update affected future plan steps.

Architecture must not drift silently.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-30/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-30/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
