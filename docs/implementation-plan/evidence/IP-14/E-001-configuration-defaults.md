# IP-14 Evidence - Configuration Defaults

Date: 2026-09-26

## Verified

- `config/defaults.toml` is the canonical public-safe default configuration.
- Drive confirmation uses bounded exponential-style backoff and a finite transition-attempt count.
- WATCHDOG idle/active heartbeat and stale thresholds are separately defined.
- LAN known-device probing, unchanged-state republish, and stray discovery have separate cadences.
- Wake timing, FETCHER heartbeat/idle lifecycle, job TTL/runtime/output bounds, and retention defaults are explicit.
- `docs/CONFIGURATION.md` documents units, rationale, expected interactions, and important coupled timing relationships.
- Tests verify TOML parsing, required sections, positive/bounded values, retry bounds, runtime ceiling, retention finiteness, and basic timing relationships.
- GitHub Actions CI run `36197689319` completed successfully for commit `4929e97730f1fe3a7f70f531e94bff9bad7aa7aa`.

## Result

IP-14 completion criteria are satisfied.
