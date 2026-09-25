# EC-36 — Plan Review Before Execution

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Before accepting the generated implementation plan, inspect it for missing prerequisites, cyclic dependencies, oversized steps, meaninglessly tiny steps, untested failure paths, protocol features with no implementation owner, implementation components with no specification owner, configuration without validation, recovery paths without failure-injection tests, and deployment tasks scheduled before required core implementation.

Correct these problems before beginning Step 2.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-36/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-36/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
