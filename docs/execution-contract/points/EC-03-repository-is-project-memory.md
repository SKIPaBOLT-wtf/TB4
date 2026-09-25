# EC-03 — Repository Is Project Memory

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Conversation history is not authoritative project state. The repository is.

Every substantial work session must start by reading `AGENTS.md`, then `docs/START_HERE.md`, then the current implementation-plan step, followed only by references relevant to that step, the actual implementation, and related tests.

Do not reread the entire repository unnecessarily. Do not reconstruct current architecture from memory if canonical files exist.

If conversation memory conflicts with the repository, the repository wins unless the user explicitly changes the design.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-03/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-03/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
