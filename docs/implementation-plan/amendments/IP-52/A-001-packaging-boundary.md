# IP-52 Amendment A-001 — Windows packaging boundary

## Problem

The original handoff wording implied that completing IP-52 alone makes a Windows target fully pilot-ready. Complete runtime composition is intentionally verified later.

## Decision

IP-52 verifies the Windows service and process-lifecycle packaging boundary:

- login-independent native Windows Service wrapper;
- deterministic external configuration location;
- install/remove/start/stop/status command path;
- no credentials embedded in the repository;
- non-interactive PowerShell/script execution contract;
- process-tree termination behavior suitable for cancellation and service shutdown.

Full FETCHER runtime composition remains owned by IP-53 and pilot readiness by IP-59/IP-60.

## Compatibility impact

No protocol change.
