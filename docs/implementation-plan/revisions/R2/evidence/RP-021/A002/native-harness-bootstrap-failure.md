# RP-021/A002 — isolated harness bootstrap failure

Source `cc0abf1e53b350e8885a2826a0f8549dae0e9269`, INTENT `RP-021-A002-0003`, same recoverable command session17189. Actual Linux x86_64 CPython3.12.3 started a new task-owned pure test harness; no system package or external credential was changed.

Pytest import stopped before collection: `ModuleNotFoundError: No module named 'py'` at _pytest/compat.py. The directory-only copy omitted pytest's installed pure top-level compatibility module. The task runner next attempted to read absent JUnit output and failed, so it did not emit the test subprocess exit. Shell launch status is not passing test evidence. No assertion/native PASS or accepted check is claimed.

Next harness-only correction verifies/copies the installed py.py regular pure module, emits/stores the actual subprocess result before optional XML processing, and selects a fresh native fixture directory. Preserve native source and all original/new assertions unchanged; retest under a new published INTENT before dependent local/hosted qualification. No native bug origin is inferred from missing test tooling.
