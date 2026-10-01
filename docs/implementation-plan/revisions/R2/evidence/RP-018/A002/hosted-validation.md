# Combined repaired-source hosted validation
Date: 2026-10-01. Source: `5627090c724d95e4bcd97fd352bef7ff9c7e2cae`. PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/31 .
Triggered by `849cfc4126dcdcef3327c1585599a98aa30a1082`; actual checkout `4ebfe5d698e76342bf3f7d4988cbfc72627c2af2`. Exact src/tools/tests/.github/protocol/config/packaging/skill/pyproject equality to the source was checked with a zero-diff Git comparison. Documentation-only checkpoints do not substitute another runtime source.

| Workflow / job | Observed result |
| --- | --- |
| [CI 36829852714 / 110263725752](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36829852714/job/110263725752) | SUCCESS; full suite 2033 passed, 18 skipped, 4 xfailed, 422.07s; native Linux key gate 33 passed; native first-run gate 34 passed. TB4_REQUIRE_FOLDER_SSH=1 makes the actual isolated SSH/server prerequisites mandatory. |
| [Progress 36829852706 / 110263725704](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36829852706/job/110263725704) | SUCCESS; 196 development tests, 6.24s; ordinary and main-base history/ledger PASS with 20 verified and the two then-pending CI intents; public scanner PASS. |
| [Desktop Linux / 110263725765](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36829852690/job/110263725765) | SUCCESS; full suite 2050 passed, 15 skipped, 4 xfailed, 322.58s; GUI 74 passed; native keys 33 passed; native first-run 34 passed. |
| [Desktop Windows / 110263726033](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36829852690/job/110263726033) | SUCCESS; full suite 1986 passed, 79 skipped, 4 xfailed, 706.42s; GUI 70 passed / 4 POSIX skips; actual native key gate 15 passed; native first-run 30 passed / 4 Linux-only skips. |

Procedures are the checked-in CI/Desktop/Progress workflows: isolated dependency installation, public scanner, native key and first-run modules, `python -m pytest`, both `tools/build_desktop.py --role ...` builds and `tools/test_desktop_distribution.py`. All required commands completed successfully (exit 0). Dedicated first-run modules: tests/security/test_private_settings_native.py, test_first_run_native.py, test_credential_persistence_native.py and test_setup_credentials_native.py. Python 3.11 x64 hosted runners, actual Qt 6.11.2 and PyInstaller 6.22.3 desktop builds.

Both Windows and Linux actual WATCHDOG/FETCHER bundles report PASS for bundle_self_test, gui_smoke, setup_gui_smoke and install_uninstall_profile_isolation. The distribution checker asserts settings_created=false and runtime_started=false, tests actual installed executables and preserves both private profile markers and the peer role through uninstall. These are isolated synthetic installations, not a home-device deployment.

Skipped tests are not accepted platform proof. CI omits optional GUI modules and Windows-native cases; Desktop Linux exercises the GUI and has 15 Windows-native skips. Windows skips Linux server/native/POSIX cases; the separate first-run log identifies three FIFO/no-follow and one pinned-directory-rename skip. Quiet full-suite logs report aggregate skip counts rather than every reason. Required folder/SSH coverage comes from the successful mandatory Linux CI fixture, and required native Windows checks ran in the Windows job. Four strict expected failures remain the historical DEF002 cancellation-race reproduction; they do not close that defect.

Final source inventory: [collected-tests.txt](collected-tests.txt), 2069 nodes collected in 0.98s; collection is not execution evidence. Earlier RP022 inventory and all failed/earlier hosted runs remain immutable and are not substituted for these results.

## Provider-reported artifact provenance
- tb4-desktop-Windows-4ebfe5d698e76342bf3f7d4988cbfc72627c2af2: ID 11147203771, 120753103 bytes, sha256:c39bf38626823d27bdd283f8224c73c4ee716a8e918220b766aac0c5988435e8; [workflow artifact](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36829852690/artifacts/11147203771).
- tb4-desktop-Linux-4ebfe5d698e76342bf3f7d4988cbfc72627c2af2: ID 11147117935, 314237255 bytes, sha256:a4c6e8a271c7c9892d7b98f791fe82201ed150f8e7d4ca3b0865ba9bdaf4f73c; [workflow artifact](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36829852690/artifacts/11147117935).
These sizes/digests were read from GitHub metadata; no claim of an independent download/hash or release signature is made. Workflow build/acceptance logs were reviewed. No installers were deployed to the owner's machines.

RP018/A002 and RP022/A001 have separate source-linked reviewed check receipts. Published data is synthetic and public-safe; private local diagnostic paths, credentials and deployment identities are excluded.
