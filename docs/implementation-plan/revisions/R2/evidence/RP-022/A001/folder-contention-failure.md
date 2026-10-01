# RP-022/A001 folder contention regression

Source: 5e3617a42ac732cb3d0d1ff7b5521fa354e0c3a5.
Desktop run 36825527562, Ubuntu22.04 job110250250880, checkout60162ac0c9c792f74267bfdf7464c05afd2efb6f.
The full suite failed with 1 failed,2023 passed,15 platform skips,4 historical strict xfails in450.76s, exit1.
Native first-run34 passed0.42s; native Linux keys33 passed0.11s; GUI74 passed1.71s.
Build/package/upload stages were skipped after the regression failure, not accepted.

Failing node: tests/drive/test_folder_store.py::test_contending_independent_helpers_have_one_winner_then_stale_rejected.
Expected exactly one ACCEPTED among two independent helper CAS requests. Observed [UNAVAILABLE,UNKNOWN], so accepted count0. Later stale-revision and final-body assertions were not reached. The original source implementation of FolderStore.connection has read/schema queries under SQLite EXCLUSIVE locking before BEGIN IMMEDIATE; concurrent retained read-lock upgrades are a hypothesis, not yet a proven cause. The folder module last changed at6d03401e16cd688687abc0bd6e92d4b37c519b8e (RP018); RP022 has not edited it.

Preserve DEF030 and reopen RP018 for scoped diagnosis/repair with historical acceptance retained. RP022 acceptance remains held. Other jobs from the same original/repaired runs are still inspected separately, never used to waive this failure. No live storage, credentials or runtime involved.

[Failed job](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36825527562/job/110250250880).
