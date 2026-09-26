# IP-44 Evidence — WAKE_BONE WakeManager

## Verified capability

WATCHDOG now owns the deterministic WAKE_BONE request flow.

- Exact WAKE_BONE object ID is read and schema-validated.
- Expired TOSS requests are never executed.
- Valid TOSS is fenced and claimed as CHEW before wake/bootstrap actions.
- Already-fresh DOG_PULSE completes without WOL or SSH.
- Offline targets receive one BONE_THROWER action before bounded probing.
- Online targets may invoke DOOR_SCRATCHER when the request allows bootstrap.
- SSH service success is never accepted as protocol readiness; only a fresh matching DOG_PULSE permits DONE.
- All waits are bounded by the minimum of request expiry, request run limit, and wake deadline.
- Result body is verified before normal CHEW -> DONE/FAILED publication.
- Ordinary wake/bootstrap failure remains WAKE_BONE_FAILED and does not become DOG_SHIT.

## Evidence

- Implementation: `src/tb4/watchdog/wake_manager.py`
- Tests: `tests/watchdog/test_wake_manager.py`
- Final test commit: `a5b805deb98fba2c4c58e4b047cc55a7e6c1aec3`
- GitHub Actions run: `36243921325`
- Test job conclusion: **success**

**Result: VERIFIED.**
