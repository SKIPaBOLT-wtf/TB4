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
   +--> docs/COACH.md when operating TB4
   |
   +--> only the protocol/config/code references required by that step or operation
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

## Operating TB4

The AI-side COACH workflow is defined in `docs/COACH.md`.

The installable ChatGPT Skill source is intentionally compact and lives under `skill/tb4/`. It points back to canonical repository/Drive sources instead of embedding a second copy of the protocol.

## Current repository state

TB4 has an implemented and tested core, Drive abstraction, WATCHDOG/FETCHER components, platform packaging, integration simulation, failure-injection coverage, efficiency budgets, and security hardening. The authoritative implementation status remains `docs/implementation-plan/manifest.yaml`; do not infer completion from this prose.

Never assume a component exists or is complete because it was discussed outside the repository. Inspect the repository and current implementation-plan evidence first.
