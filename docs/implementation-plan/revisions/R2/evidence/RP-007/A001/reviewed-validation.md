# RP-007/A001 reviewed validation

Source: `d1af5328d05f1dda9cf36a662df06f158c0252e5`. Tested PR head: `7016fe17c67a47e1a0ff9a36450aa7e4425fdb97`. Desktop PR merge build: `819de3be7b20f75d6b84427e7ea9651e8353bc3f`. PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/14 .

## Checks reviewed

- C1: stable entry and closed catalog select exactly one RELEASED exact-build/protocol/capability profile. Current R2 catalog is deliberately UNRELEASED; no legacy or imagined operational fallback. Catalog Git blob hashes and LF checkout attributes agree.
- C2: each workflow resolves fixed repository name/numeric identity with a fresh observation nonce, then all entry/instruction/schema reads use the same immutable commit; immutable bundle only exposes declared references. Simulated branch advance during fetch cannot mix revisions.
- C3: missing/oversized/hash-corrupt content, stale/offline observations, incompatible/ambiguous/unreleased/revoked profiles block. Eligibility refresh cannot replace in-flight bytes; withdrawn/changed policy or updated runtime holds new mutations while the old pin remains available for effect inspection.
- C4: host-only adapter and verified RuntimeFacts are outside device/result authority. Traversal, foreign URLs/identity, unknown fields and duplicate keys fail closed. The installable pointer template contains only entry location/retrieval; original v1 safety tests remain against the preserved historical manual. No local skill installation occurred.

## Verified runs

- Windows Python 3.11: `python -m pytest tests/coach tests/security tests/development -ra --basetemp .venv/pytest-rp007-a001`: 230 passed in 15.02s, exit 0. Collected IDs are in `collected-tests.txt` (230 in 0.18s). Both skill-creator `quick_validate.py skill/tb4` and `quick_validate.py packaging/skill-pointer/tb4` passed. Public scanner/diff and ownership-base ledger passed.
- CI https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36771495270 , job 110078741374: 860 passed, 2 optional GUI skips in 15.49s. Progress 36771495318 and 36771445806 passed.
- Desktop https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36771495558 : Linux job 110078742964 GUI 67 passed in 1.75s and full 870 passed in 13.21s; Windows job 110078742671 GUI 63 passed, 4 POSIX-only skips in 2.39s. Both roles/platforms built and passed bundled self-test, GUI smoke, install/uninstall/profile isolation.
- Remote Linux artifact 11124336991: 310729088 bytes, SHA-256 `b6932217e1e29af777c76cef54828a9b14f92d0b65c01e8b9162d1cb42439e0d`. Windows artifact 11124152433: 119086879 bytes, SHA-256 `87e0bf7fc4628f524dcc10ebf833322bc097c3471faf1538bdbd118133e94a7f`. Stored in the recorded CI run, not copied to the knowledge archive or approved for live release.

## Limits and rollback

This design/contract step uses synthetic trusted adapters. A real source adapter must verify repository/HTTPS identity, immutable Git blob bytes and genuine freshness; a nonce alone is not proof against a dishonest adapter. Runtime facts need host provenance; self-asserted build strings are not attestation. Durable pin storage, production integration and release qualification remain later gates. Eligibility check is not a runtime fencing lease or atomic revocation with a subsequent mutation. No private data, source adapter, installed skill, target, root or live protocol changed. Withdrawing a faulty entry/profile preserves in-flight inspection evidence and never downgrades protocol or replays effects.
