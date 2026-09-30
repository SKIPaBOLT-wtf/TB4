# R2 ledger validation contract

`python -m tools.development.ledger` is a read-only development tool. It does
not execute workloads, publish, auto-resume, repair records or mark acceptance.
Fetch origin first: commit evidence must be a full SHA reachable from an origin
ref. A local object or HEAD alone is not public provenance. This offline graph
check does not establish current GitHub access or replace publication readback.

Version 1 closed record schemas are in `tools/development/schemas.py`. Unknown
metadata keys fail. Public records accept only bounded reviewed prose, stable
IDs, public source SHAs and repository evidence paths. The existing secret
scanner additionally covers ledger JSONL and receipts, with path/URL restrictions.
This is defense in depth: arbitrary prose cannot be proven private-data-free by
a schema. A publication review remains mandatory; never feed raw runtime output.
Diagnostics contain fixed codes only, never offending input values.

The manifest controls step/check acceptance. Step definitions and CHECKLIST must
match it. Each completed check maps to one or more machine-readable JSON receipts
under its active attempt. Each receipt names a reviewed PASS, zero exit status,
exact public source, procedure, platform scope, negative tests, unverified scope,
privacy review, rollback boundary and a matching successful intent/outcome pair.
Markdown reports can be referenced by receipts, but are not machine acceptance.
Evidence may cover several checks in one bounded test operation when each receipt
explains its invariant; the operation remains one exact source/test scope.

Journal sequences are contiguous per step/attempt. INTENT action IDs cannot be
reused; outcomes match an outstanding intent. UNKNOWN and BLOCKED preserve that
intent until RECONCILED resolves its effects. STARTED requires a recoverable run
identity. Corrections reference prior records and preserve their original content.
The cursor must name the journal tail and all unsettled intents across journals.
An honest outstanding intent is a valid checkpoint, never passing acceptance.

The original PLAN-R2 journal predates this schema and retains its original fields;
its order, references and intent pairing are still checked. New RP records use the
strict schema. No old event is rewritten to make it look conformant.

Use `--base <public-sha>` to additionally compare append-only journal prefixes and
allowed status transitions against a fetched base. Reopening VERIFIED requires
a later attempt and explicit revalidation scope. Accepted RP-003 adds typed defect
provenance, preserved acceptance snapshots and transitive revalidation holds;
see [DEFECT_CONTRACT.md](DEFECT_CONTRACT.md) for the current contract.

Progress CI runs only the ledger tests, current-plan validation, history checks
and public-data scan. Installer CI selects product/packaging inputs; progress-only
commits do not launch builds. No runtime or installed instruction is changed.

Rollback removes validator/CI wiring in a corrective commit and restores manual
WORK_INSTRUCTION enforcement. Journal history and prior receipts remain intact.
