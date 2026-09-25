# IP-47 - Google Drive Authentication and Client Boundary

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement the real Google Drive API client boundary without placing credentials in source control or protocol objects.

## Preconditions

IP-22 and IP-16 VERIFIED.

## Inputs / authoritative references

- `DriveBackend interface`
- `SECURITY contract`

## Work

1. Choose supported Google Drive authentication mode suitable for installed WATCHDOG/FETCHER and AI-side direct connector usage.
2. Define credential loading only from local/private configuration or provider-managed connector.
3. Implement client construction and normalized auth errors.
4. Document minimum Drive permissions/scopes.
5. Add mock tests that never require real credentials in CI.

## Files / modules

- `src/tb4/drive/google_client.py`
- `docs/GOOGLE_DRIVE_SETUP.md`
- `tests/drive/test_google_client.py`

## Required invariants

- No token, private key, refresh token, or account identifier committed.
- Auth layer does not decide TB4 state transitions.

## Tests

- Missing credentials.
- Invalid auth normalized.
- Mock client construction.
- Scope/config validation.

## Failure cases

- Credential text appears in logs or exceptions.
- Public default contains private root ID.

## Completion evidence required

- Auth boundary tests pass and secret scan finds no committed credentials.

## Handoff state

Concrete Google Drive object operations can use one authenticated client abstraction.

## Amendment path

`docs/implementation-plan/amendments/IP-47/`

## Evidence path

`docs/implementation-plan/evidence/IP-47/`
