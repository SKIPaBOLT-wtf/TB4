# EC-22 — Failure Scopes

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Do not turn every failure into a global emergency.

Keep distinct scopes for command success, command partial result, command failure, command cancellation, unknown/lost result, target unavailable, target-local infrastructure fault, transport fault, protocol inconsistency, and global coordinator-blocking fault.

Use higher-severity states only when lower-scope recovery is insufficient.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-22/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-22/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
