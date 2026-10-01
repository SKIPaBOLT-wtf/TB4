# RP023 durable discovery validation: runner finalization failure

Source: `6e17e4bcf3773b85feb54e348ee70958c9e569c3`. INTENT: RP-023-A001-0022; local session 26755.

The exact source was synchronized before the selected discovery/drive/first-run/private-settings suite. Progress reached100% with594 passing marks,43skip marks and no F marks (637 selected); these are progress observations, not an accepted pytest summary. Pytest exited1 during session finalization: `_pytest.pathlib.cleanup_dead_symlinks` -> `Path.exists/stat` -> `PermissionError: [WinError5] Access is denied` for the shared pytest-current temporary entry. Its prior creator/permission origin was not established. No private ACL was reset or old directory removed. The runner did not emit a normal final summary, so the suite is unaccepted.

The task wrapper then invoked a nonexistent scanner filename (exit2); the correct `python tools/scan_public_repo.py` was independently executed under the same INTENT and passed(exit0). Full-branch `git diff --check origin/main...HEAD` passed(exit0). No network collector opt-in, deployed mutation or public raw private-path log.

Next: use a newly verified-absent task-local pytest basetemp, preserving all old temporary data. Add and run the reviewed newer-shared-observation regression before deciding whether source repair is needed; the current code may overwrite newer shared network evidence with an older local projection. This is a source-review hypothesis until reproduced. Full hosted/native/frozen gates remain required.
