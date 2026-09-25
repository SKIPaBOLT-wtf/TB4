# START HERE

TB4 is developed as a deterministic remote-work control system with explicit logical objects, verified state transitions, bounded helpers, and memorable dog/ball vocabulary.

## Read order

```text
AGENTS.md
   |
   v
this file
   |
   +--> docs/execution-contract/README.md
   |
   +--> docs/implementation-plan/README.md
   |
   +--> current implementation-plan step
   |
   +--> only the protocol/config/code references required by that step
```

## Two different progress systems

### Execution contract

`docs/execution-contract/`

Defines **how development must be performed**. Its EC-01..EC-39 points are methodology and engineering constraints.

### Implementation plan

`docs/implementation-plan/`

Defines **what concrete engineering capability is implemented next**. Each IP step has isolated evidence and amendments so completion records never become mixed with other steps.

## Canonical vocabulary

Dog/ball names are intentional project terminology. Examples include:

- `DOG_HOUSE`
- `BALL_PARK`
- `KENNEL`
- `FETCH_BALL`
- `WAKE_BONE`
- `DOG_SNOOZE`
- `DOG_SHIT`
- `BONEYARD`
- `DOG_POUND`

Humor is allowed. Ambiguity is not.

## Current repository state

At the time this entrypoint was created, the repository contains the execution contract but the implementation is not yet present. The implementation plan begins by creating the canonical project skeleton and machine-readable protocol definitions.

Never assume a component exists because it was discussed outside the repository. Inspect the repository first.
