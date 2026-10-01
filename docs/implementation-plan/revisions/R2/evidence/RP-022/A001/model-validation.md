# First-run model and dependency validation

Source: a28f755a8e8e2f6794bf3694df153f325378d419.
Intent: RP-022-A001-0008.
Run: local-exec-65190, actual Windows x64 Python3.11.9, fresh synthetic fixtures.

Command: `python -m pytest tests/security/test_first_run.py tests/security/test_first_run_native.py tests/drive/test_first_run_storage.py tests/security/test_private_settings.py tests/security/test_private_settings_native.py tests/security/test_ballpark_contract.py tests/security/test_credential_contract.py tests/coach/test_instruction_selection.py tests/drive/test_fixed_slot_commissioning.py tests/drive/test_native_commissioning.py tests/drive/test_folder_commissioning.py tests/drive/test_setup_journal.py -ra --basetemp=../rp22-model-fixture-001`.

Observed: **220 passed, 15 skipped in 500.25s**, exit0. Skips: 4 Linux-only native settings special-object/rename cases, 11 Linux server-local folder commissioning cases. Local model/source input files were synchronized to the exact published source before launch. Independent credential codec/test additions did not change any of those files while the run executed.

Reviewed behavior: same installation/nonce across restart; durable cancel/resume; stored READY invalidated; no provider probing while genuine owner choices are missing; revoked instruction profile checked again before activation; default independent activation refusal; exact credential target/purpose availability rechecked without use; UNKNOWN persisted before a callback and never replayed after lost reply/restart; changed choices frozen during UNKNOWN; stale writer refused; unsafe rollback cannot erase external action; safe stopped rollback appends a revision and invalidates readiness; fixed public error/status surfaces omit protected identity/topology/handles.

RP019 composition checks actual native Drive/Docs request adapters against the existing synthetic atomic service: exact root permission, authority/tab/domain, STORAGE_READY marker and allocated artifact identities/seals. Removed artifact, changed domain/tab, trashed authority, unready marker or revoked root permission blocks setup with no new creation. Existing maximum-capacity commissioning and instruction/credential/BALLPARK regressions passed.

Actual Linux, durable model credential integration, local UI, full regression and desktop/package gates remain outstanding. No live authorization or step acceptance is inferred.
