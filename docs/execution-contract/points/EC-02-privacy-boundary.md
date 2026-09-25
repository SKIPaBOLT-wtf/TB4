# EC-02 — Privacy Boundary

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

The public repository may describe architecture, protocol behavior, state machines, generic device roles, configuration, helper contracts, testing, failure recovery, installation, and extension points.

It must not expose private hostnames, private addresses, credentials, keys, personal infrastructure details, private network topology, private operational purpose, or private account identifiers.

Use generic identities such as `watchdog-host`, `target-a`, `target-b`, and `example-device`. Private deployment configuration remains outside public source control.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-02/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-02/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
