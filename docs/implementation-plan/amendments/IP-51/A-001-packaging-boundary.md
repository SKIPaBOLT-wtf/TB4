# IP-51 Amendment A-001 — Packaging boundary

## Problem

The original handoff text said Linux pilot hosts could already run complete WATCHDOG/FETCHER services after IP-51. That overstates this step: full runtime composition and end-to-end behavior are verified later by IP-53 and the private pilot stages.

## Decision

IP-51 owns the **Linux service packaging boundary**:

- stable CLI role entrypoints;
- deterministic external configuration paths;
- systemd unit templates;
- login-independent service execution;
- generic signal/shutdown handling;
- least-privilege service-user guidance;
- static/unit verification of the packaging contract.

IP-51 does **not** claim that the complete Drive/LAN/runtime composition is already pilot-ready. Runtime composition is exercised by IP-53 and deployment-specific readiness by IP-59/IP-60.

## Compatibility impact

No protocol compatibility impact. This amendment only corrects the completion boundary of IP-51.
