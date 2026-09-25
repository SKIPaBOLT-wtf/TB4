# EC-24 — Recovery Philosophy

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Prefer inspect -> identify authoritative state -> reconcile -> continue.

Do not default to delete -> recreate -> hope.

Automatic reconstruction is allowed only when canonical specifications make the correct reconstruction unambiguous. Ambiguous objects must be quarantined rather than destroyed.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-24/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-24/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
