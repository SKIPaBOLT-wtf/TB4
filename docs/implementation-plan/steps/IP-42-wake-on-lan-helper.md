# IP-42 - BONE_THROWER Wake-on-LAN Helper

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement local Wake-on-LAN as a deterministic helper with no protocol decision logic.

## Preconditions

IP-08 and IP-20 VERIFIED.

## Inputs / authoritative references

- `DOG_TAG capability schema`
- `Wake timing config`

## Work

1. Validate target advertises WOL capability and has required MAC/broadcast data.
2. Construct standards-compliant magic packet.
3. Send using local network helper.
4. Return explicit attempted/not-capable/local-error result.
5. Do not itself wait for host or mutate WAKE_BONE state.

## Files / modules

- `src/tb4/watchdog/wol.py`
- `tests/watchdog/test_wol.py`

## Required invariants

- WOL helper performs one action and reports fact; WakeManager owns retries/timing.
- Invalid MAC never results in best-effort guessing.

## Tests

- Magic packet bytes.
- Capability absent.
- Invalid MAC.
- Socket send failure.

## Failure cases

- Helper loops indefinitely.
- Helper writes Drive state directly.

## Completion evidence required

- Packet construction and error tests pass.

## Handoff state

WakeManager can combine WOL with probing and bootstrap.

## Amendment path

`docs/implementation-plan/amendments/IP-42/`

## Evidence path

`docs/implementation-plan/evidence/IP-42/`
