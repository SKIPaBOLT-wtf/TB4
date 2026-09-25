# IP-06 Evidence - STOP_BALL State Machine

Date: 2026-09-25

## Verified

- The unsafe early three-state draft was formally amended before implementation.
- Canonical STOP_BALL states are:
  - READY
  - LOADING
  - REQUESTED
  - RETURNING
  - ACKNOWLEDGED
  - RECYCLING
- COACH writes the request only while LOADING.
- FETCHER sees only a fully published REQUESTED state.
- FETCHER writes acknowledgement evidence only while RETURNING.
- Cancellation matching requires exact FETCH_BALL object ID, job_id, and generation.
- A stale or mismatched STOP_BALL must not cancel work.
- The execution result remains on FETCH_BALL.
- GitHub Actions CI run `36194362538` completed successfully for commit `751502fc3b7092ae9430fe420afbef762de8fed3`.

## Amendments

- `docs/implementation-plan/amendments/IP-06/A-001-safe-stop-ball-staging.md`
- Related canonical vocabulary update: `docs/implementation-plan/amendments/IP-03/A-001-stop-ball-staging-states.md`

## Result

IP-06 completion criteria are satisfied.
