# IP-47 Evidence — Google Drive Authentication and Client Boundary

## Verified capability

TB4 now has a production authentication boundary for local WATCHDOG/FETCHER Google Drive access without committing or transporting credentials through protocol objects.

- v1 uses OAuth 2.0 Desktop-app user credentials for local daemons.
- AI-side Google Drive connector authentication remains provider-managed and separate.
- Protocol v1 requires the full Drive scope because the control tree is multi-client and may contain objects created by independently authorized clients.
- Credential contents are never accepted as configuration values; only local file paths are configured.
- Missing, invalid, expired, refresh-failed, interaction-required, interaction-failed, library-missing, and client-construction failures are normalized.
- Normal background startup never launches an OAuth browser unless interactive authorization is explicitly enabled.
- Refreshed/new authorized-user tokens are written to a private local file with restrictive POSIX permissions when supported.
- Error messages report categories/exception classes rather than serializing credential contents.
- Common OAuth credential filenames and the TB4 private directory are excluded by .gitignore.
- Google provider libraries are an explicit optional installation extra, keeping protocol-only/test installations lightweight.

## Evidence

- Implementation: `src/tb4/drive/google_client.py`
- Setup/security documentation: `docs/GOOGLE_DRIVE_SETUP.md`
- Dependency declaration: `pyproject.toml` `google` extra
- Secret-path exclusions: `.gitignore`
- Tests: `tests/drive/test_google_client.py`
- Final implementation commit: `cc98b5b050c75da0c726cc56ddd96cb329279aa8`
- GitHub Actions run: `36246049273`
- Test job conclusion: **success**
- Full suite: **453 passed**

**Result: VERIFIED.**
