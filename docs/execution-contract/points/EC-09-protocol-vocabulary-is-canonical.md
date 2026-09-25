# EC-09 — Protocol Vocabulary Is Canonical

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Logical runtime objects follow the TB4 dog/ball vocabulary. Humor is intentional; ambiguity is not.

Active object names conceptually follow `<LOGICAL_OBJECT>_<STATE>`. Examples include `FETCH_BALL_READY`, `FETCH_BALL_CHEW`, `WAKE_BONE_TOSS`, and `DOG_SNOOZE`.

Once protocol names become canonical and machine-readable, do not casually rename them. A later rename is a protocol migration requiring specification update, compatibility consideration, migration decision, tests, and documentation.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-09/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-09/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
