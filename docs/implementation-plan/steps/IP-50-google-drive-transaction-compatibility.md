# IP-50 - Google Drive Transaction Compatibility Tests

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Verify StateWalker and BodyKeeper behave correctly with Google Drive API semantics, including delayed visibility and ambiguous responses.

## Preconditions

IP-24, IP-25, IP-48, IP-49 VERIFIED.

## Inputs / authoritative references

- `Verified transaction helpers`
- `Google backend`

## Work

1. Run shared backend/transaction contract tests against mocked Google behavior.
2. Simulate rename accepted but response lost.
3. Simulate body write accepted then delayed read visibility.
4. Simulate rate limiting during confirmation.
5. Verify reconciliation always stays on same file ID.
6. Confirm no folder listing is invoked during normal transaction paths.

## Files / modules

- `tests/integration/test_google_transactions.py`

## Required invariants

- Google-specific behavior must not weaken protocol invariants.
- Transaction retry remains bounded.

## Tests

- All ambiguity/delay cases above.
- Operation-count assertion for no list_children.

## Failure cases

- Backend-specific workaround bypasses FenceGuard or state validator.

## Completion evidence required

- Transaction compatibility suite passes.

## Handoff state

Real Drive bootstrap/integration can proceed with tested provider semantics.

## Amendment path

`docs/implementation-plan/amendments/IP-50/`

## Evidence path

`docs/implementation-plan/evidence/IP-50/`
