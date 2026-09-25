# IP-44 - WAKE_BONE WakeManager

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement WATCHDOG ownership of WAKE_BONE_TOSS through host wake, probe, optional SSH bootstrap, and terminal result.

## Preconditions

IP-05, IP-24, IP-25, IP-40, IP-42, and IP-43 VERIFIED.

## Inputs / authoritative references

- `WAKE_BONE state machine/schema`
- `Wake timing config`

## Work

1. Observe exact WAKE_BONE ID.
2. Validate TOSS body and expiry.
3. Claim TOSS -> CHEW via StateWalker.
4. If host unseen and WOL capable, call BONE_THROWER.
5. Wait configured initial delay then probe on bounded interval.
6. When host is online, inspect DOG_PULSE; if Fetcher absent and bootstrap capable, call DOOR_SCRATCHER.
7. Require fresh DOG_PULSE for success.
8. Write verified result then transition DONE or FAILED.
9. Never treat expired/stale request as executable.

## Files / modules

- `src/tb4/watchdog/wake_manager.py`
- `tests/watchdog/test_wake_manager.py`

## Required invariants

- All waiting is deadline-bounded.
- Ordinary target wake/bootstrap failure remains WAKE_BONE_FAILED, not DOG_SHIT.

## Tests

- Already ready target.
- WOL then ready.
- WOL then SSH start.
- Wake deadline failure.
- Expired TOSS.
- Delayed Drive state visibility.
- Target online but Fetcher unsupported.

## Failure cases

- Wake loop runs forever.
- SSH success accepted without heartbeat.
- Old wake executes after expiry.

## Completion evidence required

- WakeManager integration tests pass against fake network/Drive helpers.

## Handoff state

COACH can request target readiness through one deterministic wake channel.

## Amendment path

`docs/implementation-plan/amendments/IP-44/`

## Evidence path

`docs/implementation-plan/evidence/IP-44/`
