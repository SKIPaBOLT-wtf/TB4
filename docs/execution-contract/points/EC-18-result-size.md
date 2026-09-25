# EC-18 — Result Size

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Live control objects must remain small. Large output belongs in artifacts.

A live object may contain bounded state, timestamps, exit code, reason code, short stdout/stderr tails, artifact reference, and artifact hash.

Large command output, generated files, diagnostics, and result artifacts must not grow the live state object indefinitely.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-18/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-18/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
