# RP-018/A002 first repair validation

Source2af8bf80715fbf1ec89bef822d5ecb96b48aad51; INTENT RP-018-A002-0005; local exec15778 completed.
Windows Python3.11.9 isolated SQLite-policy/portable tests:
`python -X utf8 -m pytest tests/drive/test_folder_lock_order.py tests/feasibility/test_fixed_folder_probe.py tests/drive/test_folder_protocol.py --basetemp <fresh-task-temp> -ra`.
Observed1failed41passed3.41s, exit1. Deterministic contention returns UNAVAILABLE/UNAVAILABLE; no ACCEPTED. Read exclusion/release and original portable protocol/fixed-journal tests pass. No Linux-server qualification is claimed.
Ledger againstdf48d98b8533f84c91506f8f0d7ed38897a92a74 exits1 RECORD_SCHEMA_INVALID. Public scanner and diff check exit0. Preserve this failed candidate and diagnose closed exception codes/schema path before another repair. No root reset or retry of a provider mutation.
