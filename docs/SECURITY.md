# TB4 Security Model

R2 development: [security and failure decision gate](SECURITY_FAILURE_CONTRACT.md)
defines the unreleased native Docs role/trust matrix and mandatory qualification
blockers. The installed contract below remains applicable until reviewed migration.

TB4 is a remote-execution control system. Its Google Drive control tree is therefore a security boundary, not merely a synchronization folder.

Humorous protocol names provide memorability only. They provide **no security**.

## Trust boundaries

```text
COACH / AI
    |
    | authenticated Drive operations
    v
GOOGLE DRIVE CONTROL TREE
    |
    +---- WATCHDOG
    |       |
    |       +-- local LAN observation
    |       +-- Wake-on-LAN
    |       +-- fixed SSH service bootstrap
    |
    +---- FETCHER
            |
            +-- verified payload
            v
          RUNNER
            |
            v
        local process
```

### Google Drive control plane

Anyone able to mutate canonical TB4 control objects may be able to request execution on participating targets.

Requirements:

- the TB4 Drive tree is private to authorized principals;
- OAuth credentials stay local to the machine that uses them;
- protocol objects never contain OAuth tokens, passwords, SSH private keys, or serialized credentials;
- normal runtime uses exact canonical object IDs rather than accepting arbitrary remote paths;
- state transitions, generation fences, hashes, TTLs, and readback confirmation are integrity controls, not authorization substitutes.

Residual risk: Google Drive authorization compromise can become TB4 remote-code-execution compromise.

## COACH / AI boundary

The COACH decides intent and creates protocol requests. It does not receive local machine credentials.

It may reference a configured target capability, but private credentials are resolved by local components.

The COACH must treat mutating `GONE` or otherwise unknown-result work as unsafe to replay until current target state is inspected.

## WATCHDOG boundary

WATCHDOG owns LAN coordination, wake/bootstrap, health, repair, and maintenance.

SSH is intentionally constrained:

- the public `DoorScratcher` API has no arbitrary command/script/payload parameter;
- only fixed service-status and service-start templates are available;
- `credential_ref` is an opaque local lookup key;
- the credential material itself never belongs in Drive;
- SSH success does not prove TB4 readiness; a fresh `DOG_PULSE` does.

SSH transport error text passes through central secret redaction before becoming a human-readable report.

## FETCHER / RUNNER boundary

FETCHER accepts work only through the canonical protocol lifecycle and generation fencing.

RUNNER executes the accepted payload locally. This is intentionally powerful.

Default deployment must use an unprivileged service identity:

- Linux packages use the dedicated `tb4` user/group;
- Windows installation defaults to `LocalService`, not `LocalSystem`.

A future privileged-operation feature must be a separate local broker with:

- an explicit allowlist of privileged verbs;
- bounded typed arguments;
- local authorization policy;
- no generic shell command passthrough;
- independent audit/review.

Do not make the normal FETCHER privileged merely because one future operation may require elevation.

## Script artifact security

Large scripts use `TOY_BOX` artifacts instead of SSH command lines.

Before execution, TB4 verifies:

1. descriptor identity matches the exact Drive object ID;
2. artifact kind is `REQUEST_SCRIPT`;
3. interpreter is from the explicit allowlist;
4. suffix matches the interpreter;
5. artifact has not expired;
6. byte length matches;
7. size is under local policy;
8. SHA-256 matches.

Remote artifact identifiers never become local filenames. The local name is derived from a SHA-256 token.

On POSIX systems:

- temporary work directory: `0700`;
- materialized script: `0600`.

Temporary data is removed after execution unless explicit local debug preservation is enabled.

## Output and secret risk

TB4 cannot safely assume that arbitrary command output is non-secret.

If a requested command prints a secret, that output may be returned through the result channel by design.

Therefore:

- do not intentionally request credential dumps;
- do not use TB4 to print local token/private-key contents;
- keep output artifacts private with the control tree;
- treat result artifacts as potentially sensitive;
- retention should delete them on schedule.

Generic automatic redaction is applied to infrastructure error text where safe. It is **not** applied blindly to arbitrary command output because doing so could destroy diagnostically important bytes or create a false belief that all possible secret formats are recognized.

## Google OAuth

See `docs/GOOGLE_DRIVE_SETUP.md`.

Local OAuth material should live outside the checkout. Typical secret filenames are ignored by `.gitignore`.

TB4 writes OAuth token material with private POSIX permissions when available.

The public repository contains configuration names and paths only, never credential contents or private Drive root IDs.

## Public repository scanner

CI runs:

```text
python tools/scan_public_repo.py
```

The scanner rejects high-confidence material including:

- private-key material markers;
- common GitHub token formats;
- Google API/OAuth token formats;
- literal assigned password/client-secret/access-token/refresh-token values;
- RFC1918 private IPv4 addresses;
- literal private TB4 Drive root assignments.

The scanner is a backstop, not a complete secret-detection oracle. Human review and provider-side secret scanning remain useful.

## Logging and error policy

For public artifacts, the stricter [RP-004 privacy policy](development/PRIVACY_POLICY.md)
and closed `tb4.privacy` contracts apply. Private deployment data is not made
public by redaction. Public desktop exports use diagnostic schema v2 with fixed
codes; local telemetry remains v1 and is revalidated at the log boundary.

Private infrastructure errors must prefer:

```text
operation category
normalized outcome
exception class
bounded redacted message
```

over raw credential-bearing provider objects. Such messages remain private;
public reports use only explicitly allowlisted codes, never arbitrary exception
class names or bounded raw messages.

Google authentication errors intentionally return normalized categories and exception class names.

SSH bootstrap errors are bounded and centrally redacted.

Never log:

- credential object serialization;
- OAuth access/refresh token;
- client-secret JSON;
- SSH private-key contents;
- passwords.

## Public/private configuration separation

Public repository:

- schemas;
- protocol definitions;
- default timing values;
- generic install examples;
- service templates.

Private deployment:

- Drive root ID;
- OAuth files;
- SSH credential references and their backing material;
- target addresses/hostnames if identifying;
- local privilege policy;
- machine-specific paths where identifying.

## Dependency policy

`pyproject.toml` declares compatible lower bounds so TB4 remains installable as a Python package.

Security/reproducibility policy is layered:

1. CI tests supported dependency resolution continuously.
2. Dependabot proposes Python and GitHub Actions updates.
3. GitHub Actions used by CI are pinned to reviewed commit SHAs.
4. A real deployment should freeze its resolved Python environment/constraints and update it deliberately after CI validation.
5. Security fixes may update the frozen deployment set without changing the TB4 protocol.

The public project does not pretend that an unreviewed forever-lock is safer than actively maintained dependencies.

## Service-account permissions

The `tb4` Linux account or Windows `LocalService` account should have only:

- read access to public installation/code;
- read access to required private local configuration;
- write access to TB4-specific temporary/state directories;
- network access required for Drive and intended LAN operations.

Do not grant blanket administrator/root rights.

WATCHDOG-specific WOL or service-bootstrap permissions should be granted narrowly by platform policy.

## Repository security scan limitations

The scanner intentionally favors high-confidence patterns to avoid teaching developers to ignore noisy CI.

Residual risks include:

- unknown/new token formats;
- secrets encoded or split across text;
- sensitive data that does not resemble a credential;
- private identifiers not matching configured patterns;
- malicious commands intentionally returning secrets.

These require least privilege, review, restricted repository/Drive access, and disciplined deployment.

## Security review before pilot

Before a private real-machine pilot:

- security regression tests must pass;
- public repository scan must pass;
- private OAuth files must exist only locally;
- service identities must be non-admin by default;
- target credential references must resolve locally;
- TB4 Drive tree access must be restricted to intended principals;
- no private deployment values may be committed while preparing the pilot.
