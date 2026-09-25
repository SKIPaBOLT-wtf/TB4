# IP-54 - Integrated Failure-Injection Suite

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Prove recovery mechanisms by deliberately breaking active operations at defined points.

## Preconditions

IP-53 VERIFIED.

## Inputs / authoritative references

- `EC-28`
- `Failure recovery specs`

## Work

1. Kill/restart FETCHER during CHEW.
2. Inject stale old worker after a newer generation starts.
3. Delay/lose Drive mutation responses.
4. Create duplicate live object then run audit/repair.
5. Corrupt control body.
6. Disconnect Drive backend during active operation.
7. Simulate clock skew beyond safe threshold.
8. Interrupt bootstrap/tree repair.
9. Generate oversized output with artifact failure.

## Files / modules

- `tests/failure_injection/`
- `docs/FAILURE_RECOVERY.md`

## Required invariants

- Every injected failure ends in deterministic recovery or explicit blocking state.
- Mutating unknown-result job is never blindly replayed.

## Tests

- One test scenario per listed fault with expected final state.

## Failure cases

- Test only asserts exception rather than recovered/blocked system state.

## Completion evidence required

- Failure suite passes and recovery doc references each scenario.

## Handoff state

Efficiency and security hardening can evaluate a functionally resilient system.

## Amendment path

`docs/implementation-plan/amendments/IP-54/`

## Evidence path

`docs/implementation-plan/evidence/IP-54/`
