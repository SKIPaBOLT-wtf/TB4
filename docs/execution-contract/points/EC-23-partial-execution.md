# EC-23 — Partial Execution

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

A command may fail after producing side effects. A nonzero exit code does not mean nothing happened.

Recovery logic must distinguish DONE, PARTIAL, FAILED, CANCELLED, and GONE / UNKNOWN EFFECT.

Mutating work with an unknown result must be inspected before replay.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-23/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-23/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
