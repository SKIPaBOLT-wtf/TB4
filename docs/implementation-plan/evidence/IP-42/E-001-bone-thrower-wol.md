# IP-42 Evidence — BONE_THROWER Wake-on-LAN Helper

## Verified capability

WATCHDOG now has a one-shot Wake-on-LAN helper with no protocol decision logic.

- DOG_TAG-style `wake_on_lan` capability gates the action.
- MAC and broadcast hints are runtime/private inputs and are never guessed.
- Magic packets are standards-compliant: six 0xFF bytes followed by the six-byte MAC repeated sixteen times.
- Common MAC separators normalize deterministically.
- Invalid MAC, missing hints, invalid broadcast addresses, and invalid ports fail before network I/O.
- Socket failures and short sends are normalized as local errors.
- Exactly one datagram send is attempted per helper call.
- The helper never waits for host readiness, retries, or mutates WAKE_BONE state.

## Evidence

- Implementation: `src/tb4/watchdog/wol.py`
- Tests: `tests/watchdog/test_wol.py`
- Final test commit: `13a48b221ab2937cc61452af243b7ec0bfbb1853`
- GitHub Actions run: `36243736248`
- Test job conclusion: **success**

**Result: VERIFIED.**
