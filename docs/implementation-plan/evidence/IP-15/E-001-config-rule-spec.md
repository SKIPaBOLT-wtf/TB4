# IP-15 Evidence - Configuration Relationship Validator Specification

Date: 2026-09-26

## Verified

- `protocol/config-rules.yaml` defines machine-checkable FATAL and WARNING relationships using configuration-only references.
- WATCHDOG idle and active stale thresholds require at least three nominal heartbeat periods.
- Wake deadline must permit initial WOL delay plus multiple probes.
- GONE grace must span multiple busy FETCHER heartbeats.
- FETCHER idle exit must span multiple idle heartbeats.
- Default/max job runtime relationships and the protocol hard ceiling are explicit.
- Drive transition attempts, nondecreasing backoff, and total confirmation sleep budget are bounded.
- Warning-only efficiency relationships are separated from startup-blocking safety rules.
- Runtime-only invariants are explicitly owned by FETCHER, WATCHDOG, or DeadlineGuard instead of being falsely encoded as static TOML checks.
- The rule graph cannot reference other rule IDs, preventing circular dependencies.
- Canonical defaults satisfy every FATAL rule and constructed unsafe configurations fail their intended rules.
- GitHub Actions CI run `36197836226` completed successfully for commit `fd40481835991d97711009cb63d3fba407de9184`.

## Result

IP-15 completion criteria are satisfied.
