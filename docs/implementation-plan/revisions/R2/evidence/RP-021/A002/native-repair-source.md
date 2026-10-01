# RP-021/A002 — native held-source repair checkpoint

INTENT `RP-021-A002-0001`; exact public source `cc0abf1e53b350e8885a2826a0f8549dae0e9269`; DEF-046. Only src/tb4/linux_key_native.py and its actual-kernel security tests changed.

Held recheck retains native ownership, private mode, ACL, exact held-descriptor mount/path-chain and memfd-seal checks. It now reads current source content with positioned mutable reads bounded to MAX_KEY_BYTES+1, preserving source and borrowed snapshot offsets, compares the admitted opaque metadata/content version, checks source metadata/path again, and zeroes the mutable buffer in finally on success/failure. Availability of preadv is qualified explicitly; unsupported systems fail closed.

Added tests exercise equal timestamp observations while real kernel identity/permission/mount checks remain, distinct fresh content version, denial before fixed-helper admission, partial/failed/short/oversized/racing reads, bounded mutable buffers, all-exit zeroing, preserved offsets/snapshot and missing API refusal. Existing `test_original_mutation_cannot_change_already_admitted_snapshot` AST is exactly unchanged; whitespace diff check passed.

Review: no immutable key bytes retained, provider error/path exported, key file written by production code, helper replay, live migration or WATCHDOG takeover barrier. Tests use synthetic task-owned files only. Current RP-021–024 acceptance is held at A002; RP-025 remains BLOCKED/A001 and DEF-047 requires later helper integration repair. New tests/actual Linux and complete platform qualification remain pending; this RECORDED source checkpoint is not acceptance.
