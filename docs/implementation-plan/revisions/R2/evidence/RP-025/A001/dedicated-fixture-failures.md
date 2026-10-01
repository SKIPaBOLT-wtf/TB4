# RP-025 dedicated fixture failures

Source: `37f8c9cc1d9487edea98e7ae26b7df294a8a55ac`; local exact-source synchronization verified clean at checkpoint `476bf88e5bed9c6a5c831b3331ce47b245ec5cf4`.

Command: the dedicated `tests/drive/test_fetcher_profile.py` and `tests/drive/test_fetcher_enrollment.py` suite with `-ra`, fresh task-owned base02, Python UTF-8 and Qt offscreen. Actual pytest result: **64 passed, 8 failed in 11.04s; exit 1**. The conditional seven-file regression command did not start. Collection-order repair is exercised successfully; it is not complete acceptance.

| Cases | Measured failure and inspected cause | Required repair |
|---|---|---|
| second approved device | `ENROLLMENT_CAPACITY` before duplicate-binding assertion; reused commissioning fixture preallocates one device, second discovery observation is not allocated | Construct a fresh two-device commissioned synthetic authority through the actual existing bootstrap/commissioning adapters before observations; assert both approvals exist |
| lost-reply takeover and both stale/forced owner cases | `LEADERSHIP_IDENTITY` before takeover; reused owner enrollment map supplies `synthetic-owner` while actual leadership fixture used `synthetic-discoverer` | Use the exact already verified trusted enrollment map from the current test leader; keep the same real takeover/force calls and assertions |
| discovery refresh | `DISCOVERY_OBSERVATION`; test supplies `NETWORK_PROBE`, outside closed methods `NEIGHBOR_CACHE`, `ICMP`, `FIXED_HELPER` | Use an allowed actual observation method at the same newer trusted clock; preserve profile and shared descriptor assertions |
| private staging, promotion and readback | Expected `SettingsError` is not raised; test assigns unused `native.fail`, but `MemoryNative` uses `failure`; readback must be armed after promotion to reach the post-commit readback boundary | Inject the actual fixture failure field/callback at each requested transaction stage; preserve no authority mutation and durable recovery assertions |

Inspected old fixture/runtime definitions show these input mismatches. No production runtime defect is established by this run. Public evidence excludes machine identifiers, private roots, credential values and raw dumps. Raw task-local log `work/rp25-dedicated-02.log` remains local; the summary above preserves all measured failing cases.

RP-025 C1-C4 remain unaccepted with repair holds. Next action: publish a test-only repair INTENT for these exact fixture boundaries, then publish the changed source and retest on a new fresh task-owned base. No accepted predecessor, runtime, live device, unknown-operation replay or authority reset is included.
