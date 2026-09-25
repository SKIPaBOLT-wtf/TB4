# IP-21 Evidence - Retry and Backoff Helpers

Date: 2026-09-26

## Verified

- RetryPolicy is derived from canonical Drive confirmation backoff and transition-attempt settings.
- Confirmation probes use the exact configured nondecreasing backoff sequence.
- Retry paths are finite: empty, zero, negative, decreasing backoff values and non-positive attempt ceilings are rejected.
- A successful first probe performs no unnecessary sleep.
- Confirmation exhaustion, monotonic deadline expiry, and ambiguous remote state are reported as distinct terminal retry outcomes.
- AMBIGUOUS stops immediately and never triggers automatic mutation replay.
- OperationAttemptBudget enforces the exact configured operation-attempt ceiling and monotonic deadline.
- Clock and sleeper injection make all retry tests deterministic with no real waits.
- GitHub Actions CI run `36198493412` completed successfully for commit `f30c17a6bf299f1ecaed546cfed1d099c63846aa`.

## Result

IP-21 completion criteria are satisfied.
