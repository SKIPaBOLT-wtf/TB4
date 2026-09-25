# IP-14 - Configuration Defaults

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Create the canonical public default configuration with conservative values and documented units.

## Preconditions

IP-07 through IP-13 VERIFIED.

## Inputs / authoritative references

- `EC-19`
- `EC-20`
- `Protocol timing requirements`

## Work

1. Define Drive confirmation backoff and bounded transition attempts.
2. Define watchdog idle/active heartbeat and stale thresholds.
3. Define known-device probe, unchanged publish freshness, and stray-scan intervals.
4. Define wake delays and deadlines.
5. Define Fetcher busy/idle heartbeat and idle exit.
6. Define job accept TTL, default/max run limits, inline output limit.
7. Define retention intervals and protocol safety ceilings.
8. Document why each default is appropriate for a small home/LAN deployment without private addresses.

## Files / modules

- `config/defaults.toml`
- `docs/CONFIGURATION.md`
- `tests/config/test_defaults.py`

## Required invariants

- Defaults remain generic and public-safe.
- No single timing value is treated independently from related safety thresholds.

## Tests

- TOML parses.
- All required keys present.
- Units and positive-range constraints pass.

## Failure cases

- Missing required default.
- Unbounded retry or runtime default.

## Completion evidence required

- Default configuration parser tests pass.

## Handoff state

Relationship validation may now operate on one canonical configuration source.

## Amendment path

`docs/implementation-plan/amendments/IP-14/`

## Evidence path

`docs/implementation-plan/evidence/IP-14/`
