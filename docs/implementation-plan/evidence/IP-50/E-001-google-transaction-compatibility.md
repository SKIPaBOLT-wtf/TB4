# IP-50 Evidence — Google Drive Transaction Compatibility

## Verified capability

Shared TB4 transaction helpers preserve their invariants when used through the Google Drive provider boundary.

- A rename that applies remotely but loses its response is reconciled from the same stable file ID.
- StateWalker does not issue a second rename after an ambiguous mutation.
- Delayed body visibility causes additional readback probes, not an additional body mutation.
- A body write that applies but loses its response is accepted only after schema/hash readback confirmation.
- A rate-limit response during rename confirmation is treated as temporary read visibility loss and retried within the bounded confirmation policy.
- Persistent confirmation failure produces UNCONFIRMED rather than replaying the original mutation.
- All normal transaction cases stay on the same file ID.
- Google transaction compatibility tests prove no list_children/folder enumeration occurs on the normal control path.

## Evidence

- Integration tests: `tests/integration/test_google_transactions.py`
- Shared helpers exercised unchanged: `src/tb4/drive/state_walker.py`, `src/tb4/drive/body_keeper.py`
- Google provider: `src/tb4/drive/google_backend.py`
- Final implementation commit: `54a3391591b0534f7d3f3cd55c6bb72fe241c645`
- GitHub Actions run: `36246424419`
- Test job conclusion: **success**
- Full suite: **482 passed**

**Result: VERIFIED.**
