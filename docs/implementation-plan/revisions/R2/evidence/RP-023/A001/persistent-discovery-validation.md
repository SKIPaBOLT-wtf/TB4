# Persistent discovery targeted validation

Source: `a423b69e03bd43c756cfb1077a5920fed93b42de`. INTENT RP-023-A001-0035; local execution23280. Exact owned-source remote equality and synchronization passed. Windows isolated Python3.11.9; only synthetic service data and fresh protected test directories. No native network collector opt-in.

Command: `python -u -m pytest tests/discovery tests/drive/test_discovery_workflow.py tests/drive/test_first_run_storage.py tests/security/test_first_run.py tests/security/test_first_run_native.py tests/security/test_private_settings.py tests/security/test_private_settings_native.py --basetemp <new-task-owned-directory> -ra`.

Result:165 passed,6 skipped in4.56s; pytest exit0. Skips:2 explicit hosted-only native loopback tests;3 Linux FIFO/no-follow cases;1 Linux root-rename/pinned-directory case. Public scanner exit0; full-branch diff check exit0. No shared default pytest temp cleanup. Previous failing attempts remain unaccepted historical results.

Named coverage includes durable-before-publication identities, restart/cancel/rollback preservation, existing artifact/enrollment fields, full quarantine/retained UNKNOWN work, stale/forced takeover and post-durability supersession, lost reply inspect-only recovery, local commit failure before shared write, owner/authority/slot/artifact/generation tamper rejection, scope/capability checks and shared privacy. Actual native protected settings restart creates no per-device files. Three previously failing newer-shared-fact cases now pass; a newer local positive observation updates the same untrusted identity. Default profile and enrollment authority remain unchanged.

DEF032/033/034/035/036 stay OPEN until complete RP023 acceptance. Hosted Linux/Windows actual loopback collection, full regressions, frozen application/install gates and final review remain pending; no deployment topology acceptance.
