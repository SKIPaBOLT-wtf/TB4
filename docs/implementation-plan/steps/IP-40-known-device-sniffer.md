# IP-40 - Known-Device SNIFFER

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Probe already known devices locally at low cost and publish only meaningful changes or periodic freshness.

## Preconditions

IP-08, IP-13, IP-39 VERIFIED.

## Inputs / authoritative references

- `DOG_SNIFF schema`
- `Network timing defaults`
- `PARK_MAP`

## Work

1. Define pluggable local probe interface.
2. Probe known devices by stored local identity/address hints.
3. Compare observation with last local state before any Drive write.
4. Publish immediately on meaningful change.
5. Republish unchanged observation only at configured freshness interval.
6. Spread probes using scheduler phase offsets.

## Files / modules

- `src/tb4/watchdog/sniffer.py`
- `tests/watchdog/test_sniffer.py`

## Required invariants

- Frequent local probe does not imply frequent Drive write.
- Probe failure becomes observation evidence, not DOG_SHIT.

## Tests

- Online unchanged no write.
- Online->offline write.
- Offline->online write.
- Freshness republish.
- Probe exception normalized.

## Failure cases

- Every 20s probe writes Drive.
- One target probe failure blocks all targets.

## Completion evidence required

- Tests verify write-on-change and bounded freshness publication.

## Handoff state

WATCHDOG can maintain current known-device observations efficiently.

## Amendment path

`docs/implementation-plan/amendments/IP-40/`

## Evidence path

`docs/implementation-plan/evidence/IP-40/`
