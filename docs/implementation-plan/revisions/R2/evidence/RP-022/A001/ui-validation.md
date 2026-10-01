# Local first-run UI qualification

Source: f9d2a74102a462c9f8aee35a763ff257306d7118.
Intent: RP-022-A001-0025.
Actual Windows x64/Python3.11.9. Dependency preparation0027/0029 installed the repository-declared extras only in the task venv; imports observed Qt/PySide6 6.11.2, google-api-python-client2.201.0, tomlkit0.15.1.

Initial command: `python -u -m pytest tests/desktop/test_setup_ui.py tests/drive/test_setup_storage_selection.py tests/security/test_first_run.py tests/security/test_first_run_native.py tests/security/test_setup_credentials_native.py tests/security/test_private_settings.py tests/security/test_private_settings_native.py -ra --basetemp=../rp22-ui-fixture-001`.
Result: **77 passed, 6 skipped in1.21s**, exit0. One module skip was missing local PySide6, preserved as an unmet prerequisite rather than GUI success. Other five skips were Linux folder/special-object cases.

After dependency preparation, `python -u -m pytest tests/desktop/test_setup_ui.py -ra --basetemp=../rp22-qt-fixture-001` executed all **6 real Qt tests in0.39s**, exit0, no skips. Reviewed save/cancel/restart with stable identity and saved owner request, asynchronous checks blocking missing storage context, malformed scope preserving previous bytes, UNKNOWN action never replayed/changed, explicit private location gate refusing errors without raw provider text, and fresh-GUI/existing-v1 entry routing. Qt controls execute the actual controller/model; this fixture uses synthetic private storage, while separate native tests qualify OS persistence.

For each watchdog/fetcher role, source entry `python -m tb4.desktop.entry --role ROLE --action setup-smoke --profile-root SYNTHETIC_PROFILE --report SYNTHETIC_REPORT` returned exit0 and setup_gui_smoke=PASS, settings_created=false, runtime_started=false. The same source entry self-test returned PASS/exit0 (imports/resources/native child, no Drive). These are source-mode results, not frozen-binary evidence.

Ledger against claim base df48d98b8533f84c91506f8f0d7ed38897a92a74 at commit5a77880b1c3f156c6802ad744b010854cc327fe3 passed21verified with the then-pending UI/dependency intents. Public scanner clean; git diff --check exit0. No product test failures. Required full Linux/Windows native/platform/frozen package qualification remains outstanding; no RP022 check is accepted from this local evidence alone.
