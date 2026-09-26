# IP-41 Evidence — STRAY_HUNTER Discovery

## Verified capability

WATCHDOG can discover previously unknown LAN devices on a maintenance path without granting execution authority.

- Discovery backend is separate from the known-device probe interface.
- Stable discovery identity is selected deterministically from hardware ID, MAC, discovery token, then address-set fallback.
- Unknown devices receive deterministic `stray-<12hex>` folder names.
- Each stray folder contains one fixed `STRAY_CARD` with bounded first-seen/last-seen and observation evidence.
- Repeated unchanged discoveries do not create additional folders or rewrite STRAY_CARD.
- Address changes preserve the same stray identity when stronger stable identity remains unchanged.
- Discovery records never create BALL_PARK targets or execution capabilities.
- Devices without any deterministic identity are reported UNRESOLVED and not published.
- Duplicate deterministic stray folders fail closed for later audit/quarantine.
- STRAY_CARD was added through explicit IP-03/IP-09 amendments rather than silent protocol drift.

## Evidence

- Implementation: `src/tb4/watchdog/stray_hunter.py`
- Schema: `protocol/schemas/stray-card.schema.json`
- Tests: `tests/watchdog/test_stray_hunter.py`
- Protocol amendment commits are recorded in the implementation-plan manifest.
- Final compatibility fix commit: `ac08fbf8283e00b08471e275718c9bb288c83479`
- GitHub Actions run: `36243670614`
- Test job conclusion: **success**

**Result: VERIFIED.**
