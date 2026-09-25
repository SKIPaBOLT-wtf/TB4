# EC-13 — Ambiguous Write Rule

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

A request returning without clear confirmation is neither automatically success nor automatically failure. It is unconfirmed.

The helper must reconcile the same operation before another mutation is attempted.

Never generate a duplicate logical operation merely because remote visibility is delayed.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-13/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-13/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
