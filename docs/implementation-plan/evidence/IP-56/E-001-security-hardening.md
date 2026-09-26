# IP-56 Evidence — Security Hardening

## Verified controls

Security hardening now includes:

- documented trust model in `docs/SECURITY.md`;
- local-only credential boundary for Google OAuth and SSH references;
- central infrastructure-error secret redaction;
- public repository scanner enforced by CI;
- high-confidence scanning for private-key material, common provider tokens, assigned credential literals, RFC1918 addresses, and private root assignments;
- explicit test-only scan exceptions limited to source lines under `tests/`;
- artifact descriptor identity, expiry, size, hash, interpreter, and suffix validation;
- hash-derived local artifact filenames;
- POSIX temp directory `0700` and script `0600`;
- unprivileged Linux `tb4` service identity and Windows `LocalService` default;
- pinned GitHub Actions revisions;
- Dependabot policy for Python and GitHub Actions dependencies.

SSH bootstrap error text now passes through central redaction before it can be returned as a human-readable message.

## CI evidence

Final hardening commit:
- `a90c6f4fd06d0b4ddd7886bb70bd5669b3f35b49`

GitHub Actions:
- CI run #354
- https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36272595661
- Public repository security scan: success
- Full pytest suite: success
- Overall conclusion: success

The earlier red CI runs exposed synthetic OAuth fixture strings. The fix did not disable test scanning globally; it introduced an explicit, source-line-level test-only marker, preserving detection elsewhere.

## Residual risks documented

`docs/SECURITY.md` explicitly records that:

- Drive authorization compromise can become TB4 execution compromise;
- arbitrary command output can itself contain secrets;
- pattern-based scanning cannot recognize every future secret format;
- privileged operations must use a future separate bounded broker rather than making FETCHER privileged;
- deployment-specific root IDs, OAuth files, credentials, and identifying network data stay outside the public repository.

## Completion assessment

IP-56 is complete. Security behavior is enforced by code, CI, packaging defaults, and tests rather than depending only on developer memory.
