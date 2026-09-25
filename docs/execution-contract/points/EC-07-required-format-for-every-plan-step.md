# EC-07 — Required Format for Every Plan Step

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Every implementation-plan item must contain: Purpose; Preconditions; Inputs / authoritative references; Work; Files / modules; Required invariants; Tests; Failure cases; Completion evidence; Handoff state.

Work must be chronological and explicit. Avoid vague instructions such as “implement state management.”

Completion evidence must be objective. Handoff state must describe what the next step may safely assume.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-07/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-07/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
