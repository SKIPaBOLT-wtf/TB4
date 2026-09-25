# IP-23 Evidence - InMemoryDriveBackend

Date: 2026-09-26

## Verified

- Deterministic in-memory backend implements the provider-neutral DriveBackend contract.
- Objects use stable opaque IDs that survive rename and move.
- Exact metadata/body reads and text replacement preserve object identity.
- Expected-version mismatch returns explicit CONFLICT and does not apply the mutation.
- Delayed metadata/body visibility is deterministic and controlled by exact read counts.
- Injected AMBIGUOUS mutation may apply while returning no false success, forcing caller reconciliation.
- Injected transient failures do not apply mutations.
- Permission/not-found outcomes are normalized.
- Failure injection uses exact configured counts and no randomness.
- Operation counters expose exact call counts and are resettable for later efficiency tests.
- Maintenance listing works without becoming path identity.
- GitHub Actions CI run `36198803712` completed successfully for commit `98c3c23fea2d8feae6caf961886a63ae443a5725`.

## Result

IP-23 completion criteria are satisfied.
