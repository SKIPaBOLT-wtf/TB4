# Newer shared observation reproduction

Source `5b9314b7f6dc86875f39ec8c3d84f3df58008988`; diagnostic INTENT RP-023-A001-0031. Fresh verified-absent task-local basetemp, synthetic Docs service only. Exact local/remote test equality and branch synchronization passed.

Eight selected cases executed with normal pytest finalization: three freshness cases FAILED, five pending-plan tamper cases PASSED, pytest exit1. The newer225, expired225 and future400 shared NETWORK_PROBE facts were replaced by a local cache-only projection carrying source NONE and null observed_at/valid_for_s. The future case also incorrectly projected FRESH. This proves publication overwrites newer source/timing evidence; ownership/CAS consistency alone does not protect fact freshness. Runtime origin is `6e17e4bcf3773b85feb54e348ee70958c9e569c3`, Discovery.publish's unconditional network projection replacement.

Pending owner/authority/generation/slot/artifact tampering was rejected. The fresh task basetemp avoided the previous shared-temp finalization error; no global temp ACL or data was modified. Restored regression cases survived the whole-checkpoint and exact-source sync, resolving the reproduction precondition.

Next: preserve newer shared positive-probe evidence when the local candidate has no positive probe or an older one; compute stale/future display conservatively without removing original source/time/validity. Do not alter identity, enrollment seed/artifact bindings or ownership rules. Then rerun discovery and first-run/storage regressions before full hosted gates.
