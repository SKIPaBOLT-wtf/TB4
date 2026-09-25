# EC-06 — Step Size Rule

> **Status:** Read from `../manifest.yaml`. Do not maintain a second status here.

## Contract

Prefer smaller work items, but do not split work so finely that completion becomes meaningless.

A good implementation step normally delivers one independently verifiable engineering capability, such as one schema family, one state-machine validator, one transition helper, one fencing mechanism, one Drive primitive, one scheduler primitive, one executor primitive, one recovery mechanism, one platform service wrapper, or one integration boundary.

Split a step if it changes more than one major subsystem, introduces more than one independent protocol concept, contains multiple state machines, spans unrelated failure domains, cannot be proven complete with one focused test group, or requires too many unrelated implementation details in working context.

Do not split further if the child task has no independently observable result, cannot be independently tested, is merely a cosmetic symbol change, or would immediately require reopening the same context to finish the parent capability.

Target: small enough to understand completely; large enough to prove complete.

## Why this exists

This point is part of the persistent TB4 execution contract. Future agents must apply it without relying on prior conversation context.

## Modification path

If the meaning of this point needs to change, create an amendment under:

```text
docs/execution-contract/amendments/EC-06/
```

Do not overwrite accepted meaning silently.

## Verification path

When this point can be objectively demonstrated as satisfied, store evidence under:

```text
docs/execution-contract/evidence/EC-06/
```

Then update only the authoritative status entry in `docs/execution-contract/manifest.yaml`.
