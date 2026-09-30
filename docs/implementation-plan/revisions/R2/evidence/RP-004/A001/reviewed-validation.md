# RP-004/A001 reviewed privacy acceptance

Source: `daac7245a46862eae214ce2e02ae80ab2808231e`. Tested PR head: `4c53ef508aedf55d340a49f181e122fb03852b71`. Desktop PR merge build: `eb20829aee5e3447a8c364b3fb628210c2523730`. [PR 11](https://github.com/SKIPaBOLT-wtf/TB4/pull/11).

## Observed verification

- Windows Python 3.11: `python -m pytest tests/security tests/desktop tests/development -ra --basetemp .venv/pytest-rp004-a001`: 173 passed, 6 environment skips in 13.74 s, exit 0. Two missing local GUI imports and four POSIX-only checks were qualified separately by CI; skips were not counted as passing.
- Exact connector-written registry/manifest synchronized before final ledger/history and public scan: PASS. JSONL now participates in the repository scan. Diff/worktree clean.
- [CI 36764551422](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36764551422): 758 passed, 2 optional GUI skips in 16.09 s.
- [Progress 36764551352](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36764551352) and [36764487704](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36764487704): PASS.
- [Desktop 36764551412](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36764551412), Linux job 110055306338: GUI 67 passed in 2.01 s; full suite 768 passed in 14.94 s. Windows job 110055306121: GUI 63 passed, 4 POSIX-only skips in 2.05 s. Both jobs built WATCHDOG and FETCHER and passed bundle self-test, GUI smoke, installation/uninstallation and preservation of both private role profiles and the peer application.

CI artifact provenance (no large artifact copied into the knowledge archive): Linux artifact 11120372214, SHA-256 `a4ac82a47712db3222e7bbf58a649de81e72168bc1e8e2406e77ed6498a281b2`, 310717515 bytes; Windows artifact 11120975338, SHA-256 `40a90d75ecb6bcb13e81efbbe1989e705226214c03a722339b4a38865a0e12b0`, 119073831 bytes. Both are attached to the Desktop run above and have its merge-build suffix. They are CI artifacts, not live installations or approved releases.

## Invariant review

C1: PRIVACY_POLICY.md classifies field-level public/protected/local-secret scope, including real topology, IDs, paths and local credential handles. Unknown fields default protected. Tests enumerate secret and protected classes. No real secret or deployment configuration was collected.

C2: public diagnostic v2 has only fixed enumerated values, no arbitrary strings or timestamps. The entire artifact is schema-validated; filenames are derived from a fixed role. Worker snapshots and local logs are revalidated. PRIVATE_LLM projection carries only curated nonsecret aliases, fixed roles and capability booleans; nested bindings and credential fields are omitted and this projection cannot enter the public exporter. It is a privacy contract seed; RP-005 owns complete commissioning semantics.

C3: test_privacy_policy.py covers raw uppercase canaries, base64, hex, encoded URLs, nested dictionaries, exception messages and custom class names, protocol-name lookalikes, extra log fields, unsafe export names and stdout/stderr pipes. The same canaries cannot reach accepted report bytes, derived filenames, worker events or event logs. Screenshots/binary/raw exports are rejected for private review; no claim that arbitrary pixels can be automatically sanitized. Existing known profile/auth/recovery codes retain explicit allowlist support.

C4: documented review checks audience, filenames, metadata, encodings, image pixels, staged diff and exact readback. Containment stops publication, restricts affected artifacts, then separately authorizes revocation/rotation and verifies local replacement. Masking and hashing are explicitly insufficient. No incident response or credential changes occurred.

DEF-009 records the observed prior weaknesses (format-only code admission and unvalidated log dictionaries), with unknown originating step rather than invented attribution. Named negative tests reproduce rejection under the new boundary. Public exports intentionally change to schema v2; private worker snapshots remain v1. Unknown messages lose detail by design. Raw workload result bytes stay private and unchanged; this is not blanket sanitization of legacy internal/provider objects.

## Rollback and limits

Review covered the changed call sites, schema/data minimization, tests versus invariants, source provenance and both packaged applications. No live services, network, OAuth or installed profiles changed. Rolling back a sanitizer keeps the publication block and manual review requirement. Existing historical pilot defects remain OPEN. Public prose and binary media still require human review; arbitrary encoding is not reliably discoverable by a generic scanner.
