# TB4 Performance and Remote-Operation Budgets

TB4 is designed to remain quiet while idle. Correctness verification is never removed merely to reduce an operation count; these budgets exist to detect accidental polling, folder scans, write storms, and synchronized timer bursts.

## Design rule

```text
local observation can be frequent
remote publication must be sparse
AI polling must be rarer still
```

## Canonical public defaults

The authoritative tunable values live in `config/defaults.toml`.

Relevant defaults:

- WATCHDOG idle heartbeat: 30 s
- WATCHDOG active heartbeat: 10 s
- known-device local probe: 20 s
- unchanged known-device freshness publication: 300 s
- stray LAN scan: 600 s
- retention sweep: 3600 s
- full canonical tree audit: 21600 s

## Idle scheduler budget

WATCHDOG uses monotonic deadlines and `next_wakeup_in()`. A caller should sleep until the next deadline or an explicit event rather than call `run_due()` continuously.

For the public default schedule over one simulated hour:

- timer wakeups: <= 320;
- total timer dispatches: <= 320;
- known-device probes per device: <= 180;
- idle heartbeat dispatches: <= 120;
- stray scans: <= 6;
- retention sweeps: <= 1;
- full audits: 0 during a one-hour window.

These are conservative ceilings. They are regression alarms, not performance targets.

## Known-device publication budget

Known-device probes are local and may run every 20 seconds.

For an unchanged target:

```text
local probes every 20 s
        |
        +-- unchanged and freshness not due --> zero Drive I/O
        |
        +-- freshness due (300 s) -----------> one verified publication
```

Across ten minutes with a stable target and 31 local probes, the expected maximum is:

- 3 Drive body writes: initial, around 300 s, around 600 s;
- 0 folder listings;
- remote metadata reads only when a publication is needed.

State changes publish immediately and intentionally exceed the unchanged-state freshness cadence.

## Normal FETCH_BALL round-trip budget

The normal job path must use exact stable object IDs and perform:

```text
READY -> LOADING -> TOSS
TOSS -> CHEW -> RETURNING -> terminal
terminal -> RECYCLING -> READY
```

The integration budget requires:

- `list_children() == 0` in the live job path;
- <= 60 total in-memory backend operations for one small successful round trip;
- <= 6 rename requests;
- <= 3 body replacement requests.

The total-operation ceiling includes required remote confirmation reads. Do not optimize by removing verification or fencing.

## Phase-spread budget

Device timer phase is derived deterministically from a stable phase key.

For 64 targets on a 20-second probe interval:

- every target receives a deterministic offset in `[0, 20)`;
- target offsets must not collapse to one timestamp;
- observed spread must cover at least 15 seconds;
- no two-second bucket may contain more than 16 of the 64 targets.

This prevents a WATCHDOG restart from creating a periodic thundering herd.

## Remote listing policy

Folder enumeration is not part of the normal control path.

Allowed listing contexts include:

- bootstrap;
- discovery;
- canonical tree audit/repair;
- retention/history maintenance;
- migration/diagnostics.

Live FETCH_BALL, heartbeat, known-device unchanged observation, and health control should address known object IDs directly.

## CPU interpretation

The automated suite uses deterministic fake time rather than wall-clock CPU benchmarks because CI host load is not reproducible.

The CPU design invariant is structural:

- no busy-loop scheduler;
- no retry loop without bounded backoff/attempts;
- no unchanged-state cloud-write loop;
- missed periodic intervals are skipped rather than replayed as a burst;
- helpers expose their next deadline/event instead of requiring spin polling.

Real pilot measurements may add platform-specific CPU observations later without replacing these deterministic regression budgets.
