# IP-54 Evidence — Integrated Failure-Injection Suite

## Verified capability

The integrated failure-injection suite deliberately breaks TB4 at the nine failure boundaries required by IP-54 and checks the resulting safe or blocking state.

Covered scenarios:

1. FETCHER loss during `FETCH_BALL_CHEW` -> `FETCH_BALL_GONE`, no blind replay.
2. Stale generation tries to return after a newer generation -> `STALE_FENCE`, newer CHEW state preserved.
3. Ambiguous Drive rename -> exact-object reconciliation, no duplicate mutation.
4. Duplicate live control object -> canonical PARK_MAP identity survives, duplicate quarantined in `DOG_POUND`.
5. Corrupt FETCH_BALL body -> execution is not claimed; TOSS remains authoritative.
6. Drive read failure before claim -> TOSS remains authoritative; no fabricated terminal result.
7. Unsafe wall-clock skew -> `CLOCK_UNSAFE_FOR_TTL` -> `DOG_SHIT_BLOCKING`.
8. Interrupted bootstrap -> next run reuses partial canonical tree without duplicates.
9. Oversized output plus artifact failure -> explicit failure, temp spool cleaned, no false result artifact.

Recovery behavior is documented in `docs/FAILURE_RECOVERY.md`.

## CI evidence

- Failure-suite commit: `9d9f59a12653f6d31e9db44414adbfc476caf4a9`
- CI run #335: https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36272211519
- Result: success

- Recovery-document commit: `db7d6f5dffc05cb56b6d397e6a540f0f10569b61`
- CI run #336: https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36272243346
- Result: success

The CI workflow installs the package and runs the full `pytest` suite.

## Completion assessment

IP-54 is complete because each required injected fault reaches a deterministic recovery/blocking condition rather than merely asserting that an exception occurred. Unknown mutating work is never automatically replayed.
