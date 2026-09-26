# IP-43 Evidence — DOOR_SCRATCHER SSH Bootstrap Helper

## Verified capability

WATCHDOG now has a bounded SSH helper that can only inspect and start the installed TB4 FETCHER service.

- Public helper API has no arbitrary command/script/payload parameter.
- Linux systemd and Windows service commands are fixed templates.
- credential_ref is opaque and resolved only by the private/local transport implementation.
- Capability-disabled or incomplete targets perform no SSH.
- Already-running service, successful start, auth failure, unreachable host, local error, and start error are normalized.
- A successful start is followed by a fixed service-status recheck.
- SSH success never reports protocol readiness; `protocol_ready` remains false until WakeManager confirms a fresh DOG_PULSE.
- Output used in error messages is bounded.

## Evidence

- Implementation: `src/tb4/watchdog/ssh_bootstrap.py`
- Tests: `tests/watchdog/test_ssh_bootstrap.py`
- Final test commit: `0332d22cdd0fc3759280475a36682179db26d03e`
- GitHub Actions run: `36243805641`
- Test job conclusion: **success**

**Result: VERIFIED.**
