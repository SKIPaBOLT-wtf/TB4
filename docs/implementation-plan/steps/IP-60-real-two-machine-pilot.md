# IP-60 - Real Two-Machine Pilot

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Verify TB4 on a real coordinator and independent target using private deployment configuration while keeping public evidence sanitized.

## Preconditions

IP-59 VERIFIED and private environment access supplied.

## Inputs / authoritative references

- `docs/PILOT.md`
- `Private deployment configuration outside repo`

## Work

1. Install/enable WATCHDOG on coordinator.
2. Install/enable FETCHER on target.
3. Bootstrap or connect canonical Drive tree.
4. Verify DOG_PULSE and DOG_SNIFF freshness.
5. Test target already-online work round-trip.
6. Test target wake/bootstrap path when capability exists.
7. Test large script through TOY_BOX artifact rather than SSH command line.
8. Test PARTIAL/FAILED/CANCELLED behavior.
9. Interrupt active execution to test GONE/recovery.
10. Verify return to FETCH_BALL_READY and bounded idle behavior.
11. Publish only sanitized evidence.

## Files / modules

- `docs/implementation-plan/evidence/IP-60/`

## Required invariants

- No private credentials/addresses are committed.
- Mutating unknown-result job is inspected before retry.
- Pilot uses production helpers rather than manual state edits.

## Tests

- All pilot scenarios listed in Work.
- At least one real end-to-end failure recovery.

## Failure cases

- Environment lacks required access/capability.
- Real provider behavior violates assumed transaction semantics.
- Private information would need to be committed to continue.

## Completion evidence required

- Sanitized pilot report with scenario outcomes and relevant public commit/version identifiers.

## Handoff state

Final acceptance can evaluate both automated and real-world evidence.

## Amendment path

`docs/implementation-plan/amendments/IP-60/`

## Evidence path

`docs/implementation-plan/evidence/IP-60/`
