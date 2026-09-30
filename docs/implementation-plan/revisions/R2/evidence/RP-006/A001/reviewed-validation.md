# RP-006/A001 reviewed local credential contract

Source: `643a99063aa0c8bcb94ae0a1838852c04766f6e2`. Tested PR head: `9e4ad13a1f840f8f0305a059f48f128ea2c0737d`. Desktop merge build: `9b9d5067cc77168dbe9b46466d0d1f2fb3f74550`. [PR 13](https://github.com/SKIPaBOLT-wtf/TB4/pull/13).

## Exact validation

Windows Python 3.11: `python -m pytest tests/security tests/development tests/watchdog/test_ssh_bootstrap.py tests/desktop/test_plan.py -ra --basetemp .venv/pytest-rp006-a001`: 183 passed in 15.29 s, exit 0. Ledger/history against ownership `38e89b9a14040dda50b87a948a37558722827a26`, public scan and diff checks passed.

[CI 36768814344](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36768814344): 809 passed, 2 optional GUI skips in 16.16 s. [Progress 36768814072](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36768814072) and [36768733404](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36768733404): PASS.

[Desktop 36768814613](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36768814613): Linux job 110069663744 passed GUI 67 tests in 2.26 s and full 819 tests in 15.41 s. Windows job 110069663545 passed GUI 63 tests with 4 POSIX-only skips in 2.02 s. Both built WATCHDOG/FETCHER and passed bundle self-test, GUI smoke and installation/uninstallation preserving both role profiles and peer application.

Artifacts in that CI run: Windows 11122373520, 119079942 bytes, SHA-256 `b391ba24ace6f024e66f8b11470f185a0d4973d67f1ef09c3d446f692669985c`; Linux 11121579439, 310725176 bytes, SHA-256 `0900a2a98818f2c9bbc939e8c686abed9d58f6dbc7dc1f771cc656b8056204c5`. Neither was copied to the knowledge archive or deployed privately.

## Reviewed invariants

C1: random 128-bit opaque local handles contain no identity/path/account material. Protected binding separately scopes installation, target UUID/trust, allowed fixed status/start purposes and expiry. Tests reject target/trust/purpose mismatch and inspect reports/repr for absent handles, locators, IDs and fixture material. Arbitrary command strings cannot be a purpose.

C2: trusted local enrollment/rotation/revocation authorization is separate from incoming remote data. Only approved, permission-verified local store inspection can report READY; each invocation repeats inspection. Synthetic adapter races demonstrate required atomic permission/version/expiry rechecks at fixed use. Successful rotation verifies a new binding before revoking the old; failed candidate cleanup preserves old and unrelated bindings. No key material is deleted or modified.

C3: named tests cover ABSENT, LOCKED, EXPIRED, REVOKED, MISMATCHED, DENIED and STORE_UNAVAILABLE. Provider exceptions and raw results are not serialized. A call that may have executed returns UNKNOWN/inspection_required and never loops or retries; inspection failure does not call the adapter. Reports contain only fixed enum outcomes and booleans. Native adapter correctness is a later gate; these fixtures do not prove real ACLs or durable deduplication.

C4: test_standby_advertises_its_own_store_and_never_imports_incumbent_identity starts separate resolvers. The standby lacks the incumbent handle; an intentionally copied fixture binding is MISMATCHED with configured/available false and zero store inspections/use. A foreign-installation store is refused. No readiness is copied from a shared summary.

## Scope, review and rollback

Code/test/diff review checked the API boundary, local lifecycle, failure disclosure, per-use adapter obligations and absence of arbitrary execution. Real OS stores, keys, credential files, live SSH, private configuration and installed profiles were not accessed. Authorization arguments are trusted local policy inputs, not authentication derived from a remote boolean. Production store/ACL integration is RP-020/021 and fixed helper integration RP-036/037. Legacy OPENSSH_CONFIG behavior is not silently upgraded or migrated. SUCCEEDED is not FETCHER readiness. Provider-side revocation and durable uncertain-operation recovery remain separate authorized mechanisms.

Rollback revokes/removes only newly introduced local binding metadata, preserves unrelated credentials and reports unavailable capability; source rollback is not key deletion or live credential rotation. Historical pilot DEF-001/002 remain OPEN.
