# TB4 Configuration Defaults

`config/defaults.toml` is the canonical public default configuration. Private deployment values belong outside the public repository.

## Drive

- `confirm_backoff_ms = [250, 500, 1000, 2000, 4000, 8000]` — bounded remote readback cadence after a Drive mutation. Short first checks keep normal operations responsive; later checks avoid hammering Drive during delayed visibility.
- `transition_attempts = 3` — complete mutation attempts after confirmation failure. Increasing this improves tolerance to transient faults but lengthens ambiguous-state recovery.
- `full_audit_interval_s = 21600` — six-hour structural audit. Normal runtime must still use exact object IDs instead of scans.

## WATCHDOG

- `heartbeat_idle_s = 30`, `stale_idle_s = 90` — three nominal idle pulses may be missed before WATCHDOG is considered stale.
- `heartbeat_active_s = 10`, `stale_active_s = 35` — active work gets faster failure detection while retaining transport-delay margin.
- `awake_lease_s = 1800` — keep DOG_AWAKE cadence for 30 minutes after active work unless future policy shortens it.
- `clock_skew_tolerance_s = 10` — TTL-sensitive participants outside this tolerance require clock handling rather than silently trusting deadlines.

## Network

- `known_device_probe_s = 20` — cheap local checks for registered devices.
- `known_device_publish_s = 300` — unchanged LAN observations are refreshed remotely no more than every five minutes.
- `stray_scan_s = 600` — unknown-device discovery runs every ten minutes.

Local probing may be frequent. Unchanged probes must not become continuous Drive writes.

## Wake

- `wol_initial_wait_s = 10` — allow a target to begin booting before the first readiness sequence.
- `probe_interval_s = 5` — subsequent local readiness checks.
- `wake_deadline_s = 90` — enough for ordinary LAN targets without allowing a wake request to hang indefinitely.

## FETCHER

- `busy_heartbeat_s = 10` — active execution heartbeat.
- `idle_heartbeat_s = 60` — low-cost idle readiness evidence.
- `idle_exit_s = 600` — an ephemeral FETCHER may exit after ten idle minutes, never while a job is active.
- `gone_grace_s = 30` — additional grace after stale execution evidence before WATCHDOG may classify an active job as GONE.

## Job

- `accept_ttl_s = 120` — a published job should not become executable long after it was intended.
- `default_run_limit_s = 300` — five-minute default for ordinary commands.
- `max_run_limit_s = 21600` — six-hour protocol safety ceiling for explicitly long jobs.
- `inline_result_max_bytes = 32768` — larger results belong in TOY_BOX artifacts.
- `inline_payload_max_chars = 8192` — larger scripts belong in TOY_BOX artifacts.
- `result_tail_max_chars = 4096` — bounded diagnostic stdout/stderr tails.

The COACH may choose a smaller or larger per-job `run_limit_s`, but never beyond the configured maximum.

## Retention

- `boneyard_days = 7` — short terminal evidence retention.
- `toy_box_days = 7` — artifact retention default; live references prevent premature cleanup in later implementation.
- `sweep_interval_s = 3600` — hourly cleanup is sufficient; retention is not latency-sensitive.

## Coupled values

These defaults are not independent:

```text
heartbeat interval
      |
      v
multiple missed pulses
      +
Drive visibility allowance
      v
stale threshold
      |
      +--> gone grace for active jobs
```

Likewise:

```text
WOL initial wait + repeated probe intervals < wake deadline
```

and:

```text
default run limit <= maximum run limit <= protocol hard ceiling
```

IP-15 adds executable relationship validation so invalid combinations are rejected instead of merely documented.


## Machine-checkable relationship rules

`protocol/config-rules.yaml` is the canonical relationship specification used by later validator code.

Rules are intentionally divided by severity:

- `FATAL` — the configuration can violate timing/safety assumptions; startup must be rejected.
- `WARNING` — the configuration remains interpretable, but it is inefficient or contrary to the intended operating profile.

Rules may reference configuration values only. They do not reference other rules, which prevents dependency cycles inside the rule graph.

The specification also records runtime invariants that cannot be proven from static TOML alone, such as pausing the FETCHER idle timer while active work exists and requiring stale execution evidence before declaring a job GONE.

Drive mutation retry timing and heartbeat freshness are intentionally separate concepts. A Drive rename-confirmation backoff is not used as an invented network/heartbeat visibility allowance.
