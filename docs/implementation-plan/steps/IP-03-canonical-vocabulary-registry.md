# IP-03 - Canonical Vocabulary Registry

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Freeze canonical TB4 logical object, role, directory, and state naming before code depends on it.

## Preconditions

IP-02 VERIFIED.

## Inputs / authoritative references

- `EC-09`
- `Current public design documents`

## Work

1. Define roles COACH, WATCHDOG, FETCHER, and RUNNER with ownership boundaries.
2. Define directory names including DOG_HOUSE, BALL_PARK, KENNEL, PLAYGROUND, BONEYARD, DOG_POUND, and TOY_BOX.
3. Define active object roots including FETCH_BALL, WAKE_BONE, STOP_BALL, DOG_PULSE, DOG_TAG, DOG_SNIFF, and DOG_SHIT.
4. Define agreed state spellings including FETCH_BALL_CHEW, WAKE_BONE_TOSS, and DOG_SNOOZE.
5. Record deprecated earlier names only in migration notes, never as active aliases.
6. Add validation that canonical names are unique.

## Files / modules

- `protocol/objects.yaml`
- `docs/PROTOCOL_VOCABULARY.md`
- `tests/protocol/test_object_registry.py`

## Required invariants

- Humorous vocabulary remains intentional.
- Active control names use deterministic OBJECT_STATE form.
- No timestamp, UUID, or host-specific data appears in active control-object names.

## Tests

- Registry parses.
- Canonical names are unique.
- Required names exist exactly once.

## Failure cases

- Synonyms or old names remain active and create ambiguity.

## Completion evidence required

- Registry and documentation agree.
- Vocabulary validation tests pass.

## Handoff state

Later state-machine steps may reference canonical identifiers without renaming them.

## Amendment path

`docs/implementation-plan/amendments/IP-03/`

## Evidence path

`docs/implementation-plan/evidence/IP-03/`
