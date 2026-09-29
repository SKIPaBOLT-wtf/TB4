# IP-62 Evidence E-001 - Desktop contract and ordering

Date: 2026-09-29.

The owner explicitly added independently installable WATCHDOG and FETCHER tray
applications and requested development before a same-host private test. The
amendments preserve the old IP-60 audit and supersede only the old pilot/final
acceptance slots. IP-01..IP-59 records were not changed.

The baseline manifest was reconstructed byte-for-byte and checked against its
Git blob SHA `77a79a67472a796e0742fefa45accaba80a574ad` before editing. A structural
comparison confirmed preservation of all first 59 step records. The expanded
manifest has 70 unique steps. IP-62..IP-67 are development/build acceptance;
IP-68 is a private same-host pilot; IP-69 remains independent-machine testing;
IP-70 is expanded final acceptance. Each new step has its own file, evidence
path, amendment path, prerequisites and explicit tests.

`docs/DESKTOP.md` specifies per-role installers, profiles, controls, telemetry,
privacy, rollback, the existing API transaction boundary and development before
deployment. Mounted-folder visibility does not substitute for API confirmation.
No private host or drive-letter selection appears in public source.

Verification: local `tests/desktop/test_plan.py`, plus YAML structural comparison
and baseline blob-identity verification. This is plan/contract evidence, not
GUI, installer-build, live Drive or workstation-test evidence.
