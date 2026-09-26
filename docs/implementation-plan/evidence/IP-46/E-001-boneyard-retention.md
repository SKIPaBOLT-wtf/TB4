# IP-46 Evidence — BONEYARD Retention and Cleanup

## Verified capability

TB4 now has bounded retention for terminal history and artifacts without using deletion as a live state transition.

- DriveBackend exposes a maintenance-only permanent delete primitive.
- DeleteKeeper verifies exact parent scope, version precondition, and remote NOT_FOUND after deletion.
- Ambiguous delete is reconciled by exact object ID rather than blindly repeated.
- BONEYARD terminal summaries are small, schema-validated, deterministically named, and idempotent.
- Expired BONEYARD records are deleted at the configured boundary.
- Unexpired BONEYARD records protect their referenced TOY_BOX descriptors.
- Caller-supplied live artifact descriptor IDs protect both descriptors and their content.
- Expired unreferenced descriptors are removed, followed by content only when no surviving descriptor references it.
- Known orphan artifact content can be cleaned after the retention window.
- Unknown/malformed objects are preserved rather than guessed safe to delete.
- A false clock-safety signal blocks the entire sweep.
- A hard per-sweep delete ceiling bounds damage from clock/configuration mistakes.
- One delete failure is isolated and does not stop cleanup of unrelated eligible evidence.
- Files outside exact canonical BONEYARD/TOY_BOX parent IDs are rejected from retention deletion.

## Evidence

- Schema: `protocol/schemas/boneyard-record.schema.json`
- Backend extension: `src/tb4/drive/backend.py`
- In-memory provider: `src/tb4/drive/memory_backend.py`
- Verified delete helper: `src/tb4/drive/delete_keeper.py`
- Retention implementation: `src/tb4/watchdog/retention.py`
- Tests: `tests/watchdog/test_retention.py`, `tests/drive/test_backend_contract.py`
- Final implementation commit: `1bd8d5f06ce61d71cddba1c3d25e4a5888471717`
- GitHub Actions run: `36245896425`
- Test job conclusion: **success**
- Full suite: **442 passed**

**Result: VERIFIED.**
