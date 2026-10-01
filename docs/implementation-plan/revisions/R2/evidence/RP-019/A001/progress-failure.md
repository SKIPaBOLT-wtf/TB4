# RP-019 progress validation failure

PR28 test head `f8e99452955d53b7e251111f5805542b7b536e11`; [Progress run](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36808345887), job `110197613822`.

Development tests: 125 passed in 3.04s. Ledger: exit 1, `RECORD_SCHEMA_INVALID`. Event `RP-019-A001-0013` incorrectly says outcome `RUNNING` (closed vocabulary requires pending/started metadata) and omits `run_id`; observed text already records local session 5562 and PR28. Its bytes must remain unchanged. Add a strictly bounded append-only STARTED metadata correction; never allow changing terminal outcomes, intent scope, source identity or test results.

Independent local ledger launch first lacked PYTHONPATH and did not validate. Correct environment: local ledger exit 1 (`LEDGER_INPUT_INVALID`, pending diagnosis), scanner exit 0, diff check exit 0. Remote schema rejection above is exact and reproducible. Other CI and local focused tests were still running; this failure says nothing about their final outcomes.
