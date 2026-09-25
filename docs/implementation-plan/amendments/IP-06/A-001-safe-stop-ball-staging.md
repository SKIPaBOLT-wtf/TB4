# IP-06 Amendment A-001 - Add Safe Publication Staging States

Date: 2026-09-25

## Problem

The original IP-06 wording proposed:

```text
STOP_BALL_READY -> STOP_BALL_REQUESTED -> STOP_BALL_ACKNOWLEDGED -> STOP_BALL_READY
```

That is incompatible with the TB4 mutation contract.

If COACH renames READY directly to REQUESTED and only then writes the target `job_id` and `generation`, FETCHER can observe REQUESTED before the request body is remotely complete.

The same race exists if FETCHER moves directly to ACKNOWLEDGED before writing acknowledgement evidence.

## Decision

Protocol v1 will use:

```text
STOP_BALL_READY
    -> STOP_BALL_LOADING
    -> STOP_BALL_REQUESTED
    -> STOP_BALL_RETURNING
    -> STOP_BALL_ACKNOWLEDGED
    -> STOP_BALL_RECYCLING
    -> STOP_BALL_READY
```

Ownership:

- LOADING: COACH writes and verifies the cancel request body.
- REQUESTED: immutable published request visible to FETCHER.
- RETURNING: FETCHER writes and verifies acknowledgement evidence.
- ACKNOWLEDGED: stable acknowledgement visible to COACH.
- RECYCLING: COACH clears/reinitializes the reusable object.

COACH may also move an expired still-unclaimed REQUESTED object to RECYCLING using a verified state transition. If FETCHER already claimed it to RETURNING, the state transition conflicts safely rather than racing.

## Reason

This preserves the global TB4 rule:

```text
rename state
-> remote confirmation
-> body write
-> remote confirmation
-> publish next state
```

## Compatibility impact

No deployed protocol exists yet, so this is a pre-v1 specification correction and requires no migration.

## Affected plan steps

- IP-06
- IP-12
- IP-37
