# IP-43 - DOOR_SCRATCHER SSH Bootstrap Helper

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Start a target FETCHER through SSH without using SSH as the general TB4 command transport or embedding large scripts.

## Preconditions

IP-08, IP-30, and platform-neutral Fetcher service contract VERIFIED.

## Inputs / authoritative references

- `DOG_TAG capabilities`
- `EC-17`

## Work

1. Define minimal bootstrap command contract: start/check installed service only.
2. Define local credential reference/config interface without storing secrets in Drive or public repo.
3. Use bounded command length and fixed templates.
4. Verify remote service state/result through SSH exit/output, then require DOG_PULSE for protocol readiness.
5. Return capability/unreachable/auth/start-error results without escalating globally.

## Files / modules

- `src/tb4/watchdog/ssh_bootstrap.py`
- `tests/watchdog/test_ssh_bootstrap.py`

## Required invariants

- No arbitrary large payload is sent through SSH.
- SSH secrets remain local/private.
- DOG_PULSE, not SSH success alone, proves FETCHER protocol readiness.

## Tests

- Already running.
- Successful start.
- Auth failure.
- Host unreachable.
- Start command failure.
- Oversized/arbitrary payload API unavailable.

## Failure cases

- SSH helper becomes generic remote executor.
- Secret written to Drive/log.

## Completion evidence required

- Tests prove fixed bounded bootstrap commands and normalized outcomes.

## Handoff state

WakeManager can start installed Fetcher safely after host becomes reachable.

## Amendment path

`docs/implementation-plan/amendments/IP-43/`

## Evidence path

`docs/implementation-plan/evidence/IP-43/`
