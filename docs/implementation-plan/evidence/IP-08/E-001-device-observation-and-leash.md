# IP-08 Evidence - Device Observation and Local Fault Semantics

Date: 2026-09-25

## Verified

- DOG_TAG identity/capability semantics are defined separately from reachability.
- DOG_PULSE is the primary FETCHER readiness evidence.
- DOG_SNIFF is WATCHDOG LAN observation and uses write-on-change semantics.
- Missing/stale evidence resolves to UNKNOWN rather than fake OFFLINE.
- Fresh DOG_PULSE outranks a conflicting local probe for FETCHER readiness.
- Target-local infrastructure health uses:
  - LEASH_CLEAR
  - LEASH_TANGLED
- LEASH_TANGLED is explicitly non-global and is not an alias for DOG_SHIT.
- Offline/WOL timeout/job failure alone do not tangle the LEASH.
- GitHub Actions CI run `36194596994` completed successfully for commit `bbed99df12675fe595ccc6b6a22870242d95d93c`.

## Amendments

- `docs/implementation-plan/amendments/IP-03/A-002-target-leash-vocabulary.md`

## Result

IP-08 completion criteria are satisfied.
