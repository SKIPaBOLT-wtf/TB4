# IP-48 - Google Drive Exact-Object Operations

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement production exact-ID metadata/body/rename operations required by normal TB4 control paths.

## Preconditions

IP-22, IP-47 VERIFIED.

## Inputs / authoritative references

- `DriveBackend interface`
- `EC-11`

## Work

1. Implement get_metadata(file_id).
2. Implement read_text(file_id) and replace_text(file_id).
3. Implement rename(file_id,new_name) while preserving stable Drive ID.
4. Normalize not-found, permission, transient, rate-limit, and ambiguous outcomes.
5. Expose request identifiers/diagnostic context without leaking credentials.
6. Run backend contract tests with mocked API responses.

## Files / modules

- `src/tb4/drive/google_backend.py`
- `tests/drive/test_google_backend_exact.py`

## Required invariants

- Normal operation needs no folder listing.
- Provider-specific responses are normalized at backend boundary.

## Tests

- Metadata/read/write/rename success.
- Rate limit.
- Permission denied.
- 404.
- Ambiguous timeout after write request.

## Failure cases

- Rename implemented as create-new/delete-old and changes ID.
- Caller must parse Google error strings.

## Completion evidence required

- Exact-operation contract tests pass.

## Handoff state

StateWalker and BodyKeeper can run unchanged on the real backend.

## Amendment path

`docs/implementation-plan/amendments/IP-48/`

## Evidence path

`docs/implementation-plan/evidence/IP-48/`
