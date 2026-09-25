# EC-12 — State Mutation Contract

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Any persistent dependent operation must follow: read authoritative current state -> validate expected state -> validate ownership/fencing -> mutate state -> remote readback -> confirm mutation -> only then perform the dependent write/action.

Example: rename state -> confirm remotely -> write body.

Never rename, immediately write, and assume synchronization succeeded.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-12/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-12/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
