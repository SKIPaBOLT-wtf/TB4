# EC-01 — Purpose of This Prompt

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

This document defines how TB4 must be developed. It is not the detailed implementation specification.

Detailed protocol objects, state machines, configuration values, platform details, deployment roles, and implementation decisions belong in later implementation-plan steps and canonical repository documents.

The development method must remain usable by a strong coding agent, a weaker coding agent that can follow explicit instructions, and a human developer.

A weaker participant must still be able to continue correctly by following repository instructions mechanically.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-01/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-01/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
