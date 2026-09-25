# EC-35 — Step-Planning Algorithm

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

After this execution contract is stored as Step 1, construct remaining steps by: inspecting the repository skeleton -> classifying relevant areas as complete/specification-only/stub/partial/missing -> building a dependency graph -> identifying the smallest independently verifiable capabilities -> ordering by dependency -> applying the Step Size Rule -> assigning failure tests -> assigning integration checkpoints -> assigning deployment checkpoints -> creating the final acceptance step.

Do not invent dependencies merely to make the list orderly. Derive them from actual implementation requirements.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-35/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-35/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
