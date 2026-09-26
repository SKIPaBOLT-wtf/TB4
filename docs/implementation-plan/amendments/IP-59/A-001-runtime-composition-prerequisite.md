# IP-59 Amendment A-001 — Runtime Composition Is a Pilot Prerequisite

## Problem

The stable CLI currently declares these runtime factories:

- `tb4.watchdog.runtime:create_runtime`
- `tb4.fetcher.runtime:create_runtime`

but the corresponding runtime modules do not yet exist.

Static packaging checks can therefore pass while a real service start fails at import time. IP-60 cannot legitimately begin in that state.

## Decision

Extend IP-59 with one additional public prerequisite before private environment intervention:

1. implement explicit WATCHDOG and FETCHER runtime composition modules;
2. make them consume private deployment configuration rather than hard-coded host values;
3. construct the already-tested Google Drive/backend/helper/service components;
4. fail with sanitized, precise startup errors when required private capability is absent;
5. add runtime-factory tests that prove the CLI resolves and constructs each role without relying on conversation-only information;
6. document the exact private fields needed by each role.

## Why this belongs in IP-59

This is deployment preparation, not a new protocol feature. The protocol primitives and role components already exist; what is missing is their production composition boundary.

Deferring this to IP-60 would force code development during the real pilot and make environment failures indistinguishable from missing application wiring.

## Compatibility impact

No protocol state or object name changes.

## Completion impact

IP-59 must not become VERIFIED until both the sanitized preflight tooling and runtime composition tests pass.

## Affected later step

IP-60 may assume `tb4 watchdog` and `tb4 fetcher` resolve real runtime factories before private host access is supplied.
