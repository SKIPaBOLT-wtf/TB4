# IP-55 Evidence — Efficiency and Remote-Rate Validation

## Verified capability

TB4 now has automated structural performance budgets and documented remote-operation ceilings.

The automated suite verifies:

- WATCHDOG scheduler sleeps to deterministic deadlines rather than busy-looping;
- unchanged known-device probes perform local work without repeated Drive writes;
- the live FETCH_BALL round trip performs zero `list_children()` calls;
- normal exact-object job flow remains within a bounded remote-operation ceiling;
- deterministic phase offsets spread 64 target probe schedules across the interval.

## Measurement correction

The first budget run intentionally exposed two incorrect assumptions in the test specification:

- a 6-hour full-audit timer may legitimately have its first deterministic phase inside the first simulated hour, so the correct one-hour ceiling is `<= 1`, not `0`;
- the canonical successful BALL lifecycle contains seven renames and four body writes:
  `READY -> LOADING -> TOSS -> CHEW -> RETURNING -> DONE -> RECYCLING -> READY`.

No production verification, fencing, readback, or runtime behavior was removed to make the budget pass. Only the measured ceilings and documentation were corrected.

## CI evidence

Initial measurement:
- CI run #340: failure
- 508 tests passed; 2 new budget assertions failed due to incorrect ceilings.
- Run: https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36272344169

Corrected measured budgets:
- Commit `bba6782b6fc6bcf2b876cbf732c4c59ea757fc4d`
- CI run #341: success

Documentation aligned with measured state flow:
- Commit `f80f49a3ee2ece57004a61fbbfecbd72145d7a31`
- CI run #342: success
- Run: https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36272380966

## Documented budgets

See `docs/PERFORMANCE.md`.

Key live-path invariants:

- zero folder scans in normal FETCH_BALL work;
- unchanged known-device state publishes only at configured freshness cadence;
- scheduler wakeups correspond to due timers/events rather than polling;
- phase offsets avoid synchronized probe bursts;
- operation-count optimization may never remove required remote confirmation or fencing.

## Completion assessment

IP-55 is complete. Efficiency is now expressed as deterministic regression tests and documented budgets rather than informal expectations.
