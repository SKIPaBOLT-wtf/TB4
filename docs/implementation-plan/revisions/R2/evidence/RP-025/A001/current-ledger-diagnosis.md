# RP-025 current ledger diagnosis

Actual read-only diagnosis of clean checkpoint `d06c3628fa1a4d56457a32476d7d444f18978506` under `RP-025-A001-0025`.

All current cursor, manifest and defect JSON Schema checks pass. Direct imported `ledger.validate` then raises closed **REPAIR_ATTEMPT_REUSED** at `defects.py:145`, called from `ledger.py:517`. DEF-043 contains two repair records with the same `(RP-025,A001)` identity: original fixture repair INTENT0012 and continuation stimulus repair INTENT0017. The existing registry invariant permits one repair identity per item/attempt; subsequent bounded actions belong in that same attempt's append-only journal/evidence. The duplicate was introduced by `b89df5fcd53a94e3657fe48ba6a21ac3fed6beaf`.

The CLI's closed LEDGER_INPUT_INVALID is consistent with the validator exception crossing the __main__/imported-module boundary. No validator repair or relaxation is necessary for this task: correct the current duplicated registry identity and preserve both actual intents/outcomes/evidence.

The first diagnostic invocation attempted a nonexistent `SCHEMA` export and failed before validation. After inspecting the actual `REGISTRY_SCHEMA` name, the bounded follow-up ran successfully, reporting only schema paths, exception type, closed code and source frame names/lines. No invalid field values, private roots or provider dumps were published. Diagnosis is not a ledger PASS.

Next: current DEF-043 retains its original A001 repair record, records the follow-up INTENT0017 in notes/hypothesis/evidence, and preserves all immutable journals and sources. DEF-044 tracks this bookkeeping correction with C1-C4 holds. Then revalidate complete current/history before draft PR.
