# RP-019 A001 first validation — failed

Source: `78e4f580af1d412fdb7e3dea9ccb345ca36a0564`.
Windows Python 3.11.9, `python -X utf8 -m pytest tests/drive/test_fixed_slot_commissioning.py tests/drive/test_native_commissioning.py tests/drive/test_setup_journal.py tests/drive/test_folder_commissioning.py --basetemp <fresh-task-owned-root>`.

Observed file-backed receipt: **22 failed, 25 passed, 11 skipped in 1.74s; exit 1**. Eleven skips require a Linux server-local filesystem and remain untested here. All 22 failures report `FORCE_GENERATION`: leadership epoch 1 versus the empty force record's generation 0. This prevents reaching allocation and proves the new seed is incompatible with the already accepted RP016 invariant. DEF-022 retains this failure. No required gate is accepted.

The preceding invocation's output was lost by a wrapper error persisting an absent session ID. Its pytest cache contains the same affected node IDs but no reliable aggregate/exit receipt. It is not counted as a pass or an exact duplicate result. The safe synthetic test was repeated with a fresh root and durable log/exit files; no unknown external action was replayed.
