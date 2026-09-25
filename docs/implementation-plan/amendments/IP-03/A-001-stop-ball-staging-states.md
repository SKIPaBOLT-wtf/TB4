# IP-03 Amendment A-001 - STOP_BALL Safe Staging States

Date: 2026-09-25

## Change

The canonical STOP_BALL state vocabulary is expanded from the early draft:

```text
READY -> REQUESTED -> ACKNOWLEDGED
```

to the safe publication lifecycle:

```text
READY
-> LOADING
-> REQUESTED
-> RETURNING
-> ACKNOWLEDGED
-> RECYCLING
-> READY
```

## Reason

The original compact form exposed a race where a consumer could observe REQUESTED or ACKNOWLEDGED before the corresponding body write had been remotely verified.

This amendment keeps the already accepted STOP_BALL logical object name while adding the staging states required by the global TB4 mutation contract.

## Compatibility impact

Pre-v1 only. No deployed migration is required.

## Related amendment

`docs/implementation-plan/amendments/IP-06/A-001-safe-stop-ball-staging.md`
