# EC-17 — Script and Payload Execution

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Do not regress to giant remote one-line shell commands.

Small trivial commands may be inline. Larger scripts must use an artifact flow: prepare script artifact -> calculate integrity hash -> transfer -> verify integrity -> create local temporary script -> execute with native interpreter -> capture result -> clean according to policy.

Transport and execution remain separate abstractions. Bootstrap transport must not automatically become the general command transport.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-17/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-17/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
