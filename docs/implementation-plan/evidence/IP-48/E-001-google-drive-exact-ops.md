# IP-48 Evidence — Google Drive Exact-Object Operations

## Verified capability

The Google Drive v3 backend now implements the exact-ID operations required by normal TB4 control paths.

- get_metadata(file_id) reads only the requested object and normalizes Drive metadata into TB4 ObjectMetadata.
- read_text(file_id) uses exact metadata plus exact media reads.
- replace_text(file_id) updates the same Drive object ID.
- rename(file_id,new_name) is a single same-ID Drive metadata update rather than create/delete.
- Google file version is exposed as a version token and checked before mutation when supplied.
- The backend explicitly advertises that Google Drive does not provide a documented atomic version precondition for these v3 updates; generation fencing and verified readback remain required.
- Provider 404, permission, conflict, rate-limit, server, and ambiguous transport outcomes are normalized.
- Mutation failures whose application cannot be known are AMBIGUOUS rather than blindly retryable.
- Provider request identifiers are carried as structured diagnostic context without exposing credentials.
- Exact-operation tests assert that list_children is never invoked.

## Evidence

- Implementation: `src/tb4/drive/google_backend.py`
- Provider capability model: `src/tb4/drive/backend.py`
- Normalized diagnostics: `src/tb4/drive/errors.py`
- Tests: `tests/drive/test_google_backend_exact.py`
- Final implementation commit: `d92df262d30fdb4fa9f45935d2593122cde427ff`
- GitHub Actions run: `36246193889`
- Test job conclusion: **success**
- Full suite: **466 passed**

**Result: VERIFIED.**
