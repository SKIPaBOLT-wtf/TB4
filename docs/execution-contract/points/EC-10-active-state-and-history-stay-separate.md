# EC-10 — Active State and History Stay Separate

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

The live control path must remain deterministic and compact. Dynamic historical evidence belongs outside the live control path.

Live deterministic control objects belong in the active tree such as `BALL_PARK`. Historical evidence belongs in `BONEYARD`. Malformed or ambiguous objects belong in `DOG_POUND` rather than being silently deleted.

Maintain this separation across later implementation decisions.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-10/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-10/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
