# IP-56 - Security Hardening

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Audit trust boundaries, secret handling, local privilege, artifact execution, and public/private configuration separation before real deployment.

## Preconditions

IP-47 through IP-55 VERIFIED.

## Inputs / authoritative references

- `EC-02`
- `Security requirements`
- `Drive auth boundary`
- `Runner/artifact protocol`

## Work

1. Document threat model for Drive control plane, WATCHDOG, FETCHER, local SSH bootstrap, and artifacts.
2. Add repository secret scanning configuration/check.
3. Audit logs/errors for credential leakage.
4. Validate artifact path, size, hash, interpreter allowlist, and temporary-file permissions.
5. Document least-privilege service accounts and privileged-operation extension boundary.
6. Audit dependency pinning/update policy.
7. Review public docs for private deployment leakage.

## Files / modules

- `docs/SECURITY.md`
- `.github/`
- `tests/security/`

## Required invariants

- No credential is stored in Drive protocol objects or public repo.
- Security controls must not depend on obscurity of humorous names.

## Tests

- Secret-pattern fixtures caught.
- Path traversal rejected.
- Interpreter allowlist.
- Permission-sensitive config checks.
- Public-doc private-field scan.

## Failure cases

- Hardening relies on manually remembering not to log secrets.
- Fetcher runs privileged by default without requirement.

## Completion evidence required

- Security test suite passes and threat model documents residual risks.

## Handoff state

AI integration and pilot deployment can rely on explicit trust boundaries.

## Amendment path

`docs/implementation-plan/amendments/IP-56/`

## Evidence path

`docs/implementation-plan/evidence/IP-56/`
