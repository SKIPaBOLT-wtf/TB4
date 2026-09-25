# IP-04 Amendment A-001 - Stage GONE Through RETURNING

Date: 2026-09-25

## Problem

The first FETCH_BALL state machine allowed:

```text
FETCH_BALL_CHEW -> FETCH_BALL_GONE
```

owned by WATCHDOG.

That publishes a terminal state before WATCHDOG has a state in which it can safely write and remotely verify the lost-result evidence body.

A COACH could observe GONE while the body still contains stale CHEW-era data.

## Decision

Replace the direct edge with:

```text
FETCH_BALL_CHEW
    -> FETCH_BALL_RETURNING       // WATCHDOG wins ownership if FETCHER is truly lost
    -> write + verify GONE evidence body
    -> FETCH_BALL_GONE
```

Add:

- `CHEW -> RETURNING`, actor WATCHDOG, reason `fetcher_lost_beyond_grace`;
- `RETURNING -> GONE`, actor WATCHDOG, reason `verified_lost_result_evidence`.

Remove:

- direct `CHEW -> GONE`;
- GONE body-writer ownership.

## Race behavior

If FETCHER is still alive and concurrently attempts its normal:

```text
CHEW -> RETURNING
```

only one verified state transition wins.

The loser must reconcile the exact object state and fence rather than overwrite the winner's result.

## Compatibility impact

Pre-v1 specification correction. No deployed migration required.

## Affected later steps

- IP-11 FETCH_BALL body schema
- IP-24 StateWalker
- IP-25 BodyKeeper
- IP-35 FETCHER pipeline
- IP-45 WATCHDOG health/recovery
