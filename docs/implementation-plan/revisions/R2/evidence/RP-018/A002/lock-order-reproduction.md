# RP-018/A002 deterministic contention reproduction

Diagnostic source a163edded13dbf34721e938983326b010d4f759c; unchanged FolderStore originated at6d03401e16cd688687abc0bd6e92d4b37c519b8e.
Test: tests/drive/test_folder_lock_order.py::test_preflight_read_contention_does_not_leave_both_cas_without_winner.
Command: python -X utf8 -m pytest tests/drive/test_folder_lock_order.py --basetemp <fresh-isolated-task-directory> -ra.
Windows Python3.11.9 actual SQLite policy, not a Windows folder-server qualification. Native FolderConfig verification is replaced only in this portable test fixture; Linux uses actual qualification.
Observed:1 failed in1.05s, pytest exit1. Both replies [UNAVAILABLE,UNKNOWN], accepted count0, matching hosted Linux failure at RP022/A001/folder-contention-failure.md.

The test allows both real SQLite connections to reach the preflight count read, then delays the failed BEGIN IMMEDIATE caller before releasing its connection. This models descheduling while that process retains a shared read lock. The competing writer cannot upgrade/commit before its bounded busy timeout; the original code began its CAS and correctly conservatively reports UNKNOWN. No test fakes SQLite results or claims provider success.

Proven mechanism: EXCLUSIVE locking mode retains read locks after metadata queries; it does not itself acquire exclusive ownership before those queries. Starting from retained SHARED locks allows an upgrade conflict. The bounded scheduling fixture reproduces the mechanism; the exact incidental scheduler timing of the earlier hosted failure is not independently captured.

Proposed minimal repair: explicitly acquire and release an empty EXCLUSIVE transaction immediately after selecting EXCLUSIVE connection mode, before any schema/page reads. The mode retains that exclusive lock until connection close. Keep PERSIST/FULL, exact identities, native verification, bounded timeout, CAS/revision and UNKNOWN handling unchanged. No new lock object/root or retry/replay.

References: [SQLite locking mode](https://www.sqlite.org/pragma.html#pragma_locking_mode), [SQLite transaction semantics](https://www.sqlite.org/lang_transaction.html). No private fixture paths, topology or secrets published.
