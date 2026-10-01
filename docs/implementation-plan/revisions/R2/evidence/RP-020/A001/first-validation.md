# RP-020 A001 first validation

Source: `bc3b5a42c66defebda12255b407b76b6b9e404e6`. Test INTENT: RP-020-A001-0004.

- Focused Windows Python 3.11 credential suite: **85 passed in 0.22s**, exit 0.
- Exact collection: **85 tests in 0.05s**, exit 0.
- Public scanner: clean, exit 0. Ownership-base-to-head diff: clean, exit 0.
- Ledger against `de95f899c29f11a3cf12113af4288a838cd9b9cc`: **RECORD_SCHEMA_INVALID**, exit 1.

Read-only source inspection identifies lowercase action_id values in new RP020
journal records; the existing schema requires uppercase ASCII identifiers.
No credential test failed. Acceptance is held for this development-record defect.
Original journal bytes must be preserved. A narrow append-only case correction
must neither change action grouping, scope, source, execution nor outcome.

Before the tests, non-destructive Git sync refused known untracked source files.
Their exact published contents were verified, only those files staged, and sync
then completed without deletion or unrelated changes. Python launched once;
the refused sync did not run native tests. No live credentials were inspected.
