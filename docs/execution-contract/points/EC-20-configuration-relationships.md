# EC-20 — Configuration Relationships

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Timing variables must be validated as a system rather than as independent knobs.

For example, a stale threshold must exceed several heartbeat periods plus expected transport visibility allowance.

Changing heartbeat interval may require validation or adjustment of stale threshold, gone grace, wake timeout, and poll schedule. Encode these relationships where practical so invalid combinations are rejected.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-20/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-20/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
