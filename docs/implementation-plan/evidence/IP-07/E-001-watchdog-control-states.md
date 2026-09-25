# IP-07 Evidence - WATCHDOG Control States

Date: 2026-09-25

## Verified

- WATCHDOG activity mode is separate from health:
  - `DOG_SNOOZE`
  - `DOG_AWAKE`
- Global fault lifecycle is defined:
  - `DOG_SHIT_CLEAN`
  - `DOG_SHIT_BLOCKING`
  - `DOG_SHIT_REVIEWED`
- COACH acknowledgement does not itself clear a blocking fault.
- WATCHDOG must revalidate the failed invariant before CLEAN.
- Ordinary target/job failures are explicitly nonblocking.
- Diagnostic reads and repair remain possible while normal new work is blocked.
- GitHub Actions CI run `36194446530` completed successfully for commit `9df493dd77761f9afdd8d39b2c4046dc6cead9ce`.

## Result

IP-07 completion criteria are satisfied.
