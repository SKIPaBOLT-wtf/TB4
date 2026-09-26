# Google Drive Authentication

TB4 uses the Google Drive API as its canonical persistent control-plane transport. Authentication is deliberately separated from protocol state: OAuth credentials are local machine secrets and never belong in Drive control objects or this repository.

## v1 authentication choice

WATCHDOG/FETCHER use **Google OAuth 2.0 user credentials for a Desktop application**.

The AI-side Google Drive connector is separately authenticated by its provider. It does not read or reuse the local OAuth files.

TB4 protocol v1 requests:

```text
https://www.googleapis.com/auth/drive
```

This is intentionally broader than `drive.file`. The TB4 control tree is multi-client: objects may be created by the local daemon or by an independently authorized AI-side Drive connector. Google's `drive.file` scope is per-file access and does not guarantee that one client can mutate files created by another client merely because they share a parent folder.

TB4 compensates at the application layer by operating only on the configured TB4 root and exact object IDs. The OAuth token itself remains powerful and must be protected accordingly.

Official references:

- https://developers.google.com/workspace/drive/api/quickstart/python
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- https://developers.google.com/identity/protocols/oauth2/scopes

## Google Cloud setup

1. Create or choose a Google Cloud project.
2. Enable the Google Drive API.
3. Configure the Google Auth consent screen for the account that will own/use the TB4 Drive tree.
4. Create an OAuth 2.0 **Desktop app** client.
5. Download the client-secrets JSON to a private local directory.
6. Never copy that JSON into the repository.

For a local checkout, a suitable private layout is:

```text
~/.config/tb4/
├── google-client-secrets.json
└── google-token.json
```

The repository ignores common local credential filenames, but that is a safety net rather than permission to keep credentials inside the checkout.

## Local configuration

The authentication boundary reads paths from local configuration/environment:

```text
TB4_GOOGLE_CLIENT_SECRETS=/private/path/google-client-secrets.json
TB4_GOOGLE_TOKEN=/private/path/google-token.json
```

These values are paths only. Credential contents must never be environment variables, protocol fields, logs, BONEYARD records, or Drive objects.

Install the provider libraries with:

```bash
python -m pip install -e ".[google]"
```

## First authorization

First authorization must be an explicit local action. Construct `GoogleAuthConfig` with `allow_interactive=True` and call `build_google_drive_client`.

The local OAuth flow opens/uses the Google authorization page and writes the resulting authorized-user token file locally. Later service starts use that token without interactive login and refresh it when possible.

Normal background service startup must use `allow_interactive=False`. If authorization is missing or invalid it must report a normalized authentication outcome instead of silently launching a browser.

## Token protection

TB4 writes the token with private POSIX permissions when the platform supports them:

```text
parent directory: 0700
token file:       0600
```

Windows/filesystems without POSIX modes require equivalent operating-system ACL protection in the deployment step.

Never print:

- access tokens;
- refresh tokens;
- client secrets;
- serialized credential JSON.

Error messages report only normalized categories and exception class names.

## Root isolation

Authentication and TB4 tree authorization are different layers.

OAuth establishes which Google account/API client is allowed to call Drive. Later provider steps enforce the configured TB4 root ID and exact object operations. The public repository must not contain a private deployment root ID.

## Why service accounts are not the v1 default

Service accounts are useful for Google Workspace shared drives, but Google documents that service accounts do not have storage quota and cannot own files. A personal-drive deployment therefore has extra ownership/storage complications. TB4 v1 uses user OAuth for the general personal Drive case; a future provider mode may add service-account/shared-drive support without changing the protocol.

## Failure behavior

The client boundary normalizes:

- missing local credential files;
- invalid token files;
- refresh failure;
- required interactive authorization;
- failed interactive authorization;
- missing client libraries;
- Drive service construction failure;
- unsupported scope configuration.

None of those errors directly decides FETCH_BALL, WAKE_BONE, or DOG_SHIT state. Higher layers classify the resulting operational impact.
