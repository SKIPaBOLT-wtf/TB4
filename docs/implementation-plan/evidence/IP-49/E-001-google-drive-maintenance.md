# IP-49 Evidence — Google Drive Maintenance Operations

## Verified capability

The Google Drive provider now implements explicit maintenance operations required by bootstrap, audit, repair, discovery, and retention while keeping normal state lookup exact-ID only.

- create_folder creates a Drive folder under one exact parent ID.
- create_text uploads UTF-8 text under one exact parent ID.
- move uses files.update addParents/removeParents and preserves the original object ID.
- list_children uses a parent-ID query, excludes trash, follows every page token, supports shared drives, and returns duplicate names as distinct objects without choosing a winner.
- incomplete searches and pagination/provider failures are rejected instead of returning silently partial children.
- permanent delete supports retention files but TB4 v1 refuses folder deletion.
- expected Drive versions are checked before move/delete when supplied.
- maintenance operations expose counters and an optional observer hook.
- parent IDs are escaped as Drive query literals.
- exact-path tests continue to prove no hidden list call occurs during normal object operations.

## Evidence

- Implementation: `src/tb4/drive/google_backend.py`
- Tests: `tests/drive/test_google_backend_maintenance.py`, `tests/drive/test_google_backend_exact.py`
- Final implementation commit: `6d953da67d4a40e15de7b04a62f3e529b68e3f3b`
- GitHub Actions run: `36246311797`
- Test job conclusion: **success**
- Full suite: **477 passed**

**Result: VERIFIED.**
