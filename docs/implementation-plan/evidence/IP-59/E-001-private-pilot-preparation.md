# IP-59 Evidence E-001 — Private Pilot Preparation

## Scope

Verifies the public preparation boundary required before any private two-machine pilot work begins.

## Verified public artifacts

- `docs/PILOT.md` documents the private configuration workflow, Drive authorization/bootstrap sequence, timing profile, rollback, and sanitized evidence rules.
- `config/examples/pilot.example.toml` provides a public-safe template without private deployment values.
- `tools/preflight.py` delegates to the tested pilot preflight implementation.
- `src/tb4/watchdog/runtime.py` provides the production WATCHDOG runtime composition boundary.
- `src/tb4/fetcher/runtime.py` provides the production FETCHER runtime composition boundary.
- The stable CLI resolves `tb4.watchdog.runtime:create_runtime` and `tb4.fetcher.runtime:create_runtime`.
- Pilot tests cover CLI checks, deterministic config generation, deployment adapters, WATCHDOG runtime, FETCHER runtime, and preflight behavior.

## Independent CI evidence

GitHub Actions CI for commit:

`4119033d1e0a53c1bc13f9412f37f4606c2a25a3`

Run:

https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36276012787

Observed:

- package installation: PASS
- public repository security scan: PASS
- complete pytest suite: **566 passed in 9.36s**
- no private pilot values were required by CI

The security scan reported:

`TB4 public repository security scan: clean`

## Completion assessment

IP-59 completion criteria are satisfied:

1. generic pilot checklist and validation tooling exist;
2. private values remain outside the repository;
3. role-specific runtime factories exist and are exercised by tests;
4. public configuration can be validated without starting production services;
5. rollback and Drive preservation rules are documented;
6. CI confirms the public preparation layer is internally consistent.

## Handoff

IP-60 may now assume the public TB4 implementation is ready for private environment configuration and a real two-machine pilot. No private deployment identifiers are recorded in this evidence.
