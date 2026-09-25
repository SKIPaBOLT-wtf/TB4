# EC-29 — Machine-Readable Specification

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Where practical, protocol truth should exist in machine-readable form.

Suitable canonical sources include `protocol/state-machines.yaml`, `protocol/objects.yaml`, `protocol/tree-blueprint.yaml`, `protocol/schemas/`, and `config/defaults.toml`.

Runtime code and tests should consume or validate against these sources rather than maintaining unrelated duplicate definitions.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-29/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-29/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
