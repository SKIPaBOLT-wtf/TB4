# IP-40 Evidence — Known-Device SNIFFER

## Verified capability

WATCHDOG can probe already-known devices frequently without turning each local probe into a Google Drive write.

- Local probe implementation is pluggable.
- Each target is isolated from other targets.
- Meaningful ONLINE/OFFLINE/UNKNOWN or address/probe/MAC changes publish immediately.
- Unchanged observations produce no Drive write before the freshness deadline.
- Unchanged observations are republished only when freshness expires.
- Probe exceptions are normalized to UNKNOWN evidence rather than raised as global faults.
- Publication uses exact DOG_SNIFF object IDs and performs no folder scans.
- Remote write visibility is confirmed with bounded retry/backoff.
- Remote sequence continues from the higher of local or stored sequence values.

## Evidence

- Implementation: `src/tb4/watchdog/sniffer.py`
- Tests: `tests/watchdog/test_sniffer.py`
- Final test commit: `59d08ca4d60a8dad50f943b903f8c99eed566d07`
- GitHub Actions run: `36243454824`
- CI conclusion: **success**

**Result: VERIFIED.**
