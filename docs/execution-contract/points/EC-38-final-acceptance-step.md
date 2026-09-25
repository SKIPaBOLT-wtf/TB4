# EC-38 — Final Acceptance Step

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

The final implementation-plan item is verification, not feature development.

It must independently verify specification, core safety, remote control plane, runtime services, result handling, recovery, efficiency, security, integration, documentation, and reproducibility.

The project is complete only when it is specified, implemented, unit tested, integration tested, failure tested, pilot verified, documented, and reproducible. Code existing is not sufficient.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-38/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-38/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
