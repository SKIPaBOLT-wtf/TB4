# Initial validation (not acceptance)

Source: 82f8977d8f8b84d9e2ba067f4c0c5df332be5455; test checkpoint: b42e04a8d81a2598faaa86e16f16d34f8569eadf.

Windows Python 3.11 isolated environment, synthetic fixtures only:
- `python -m pytest tests/development -ra`: 36 cases reached 100%; process exit 1 in pytest temporary-directory cleanup (PermissionError / WinError 5 on a pre-existing pytest-current entry). Not accepted as passing.
- `python -m tools.development.ledger`: exit 0, all 64 steps parsed, zero accepted, pending test intent represented.
- Same validator with `--base bf18f8fee79655f949fa4ae41617368c80d3dc0d`: exit 0, history preserved.
- `python tools/scan_public_repo.py`: exit 0; `git diff --check`: exit 0.

Linux Progress run [36755836652](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36755836652) completed successfully at the exact test checkpoint. Only Progress was created for that documentation-only push; no installer workflow ran.

Next: isolate the Windows test temporary root within the development workspace and repeat the targeted test command. Do not delete or alter the unrelated old temporary directory. No product runtime changes or live acceptance.
