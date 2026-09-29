# IP-63 Evidence E-001 - Profiles and diagnostics

Date: 2026-09-29.

Implemented role-isolated local profiles, OS-held locks, bounded TOML reads,
production-validator delegation, optimistic save preconditions, atomic replacement
and previous-configuration backup. Implemented bounded allowlisted observations,
stale/unknown handling, private log rotation and diagnostic export filtering.
The observer forwards existing backend operations and does not add remote reads;
mutation receipts are not treated as confirmed remote metadata observations.

The support implementation is commit
`1274bb4d8c4ce17fdda5f97648a018cb7f9a416f`.
GitHub Actions PR integration run:
https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36617670288

The checkout was synthetic merge `359618ff551be0a99b62e9fd9bd9fff6a2838cbc`,
combining that head with unchanged baseline `e8e2afbe7d916177c357772b7fb8ee565d694688`.
The complete repository suite passed **603 tests in 9.82 seconds** and the public
security scan reported clean. The new isolated local support tests also passed
before upload (35 profile/telemetry cases plus two plan checks).

Coverage includes role separation, duplicate lock acquisition, released locks,
invalid configuration, comments/extensions preservation, concurrent edit refusal,
backup restore, validation failure, mutation/readback distinction, stale time,
malformed worker input, bounded histories and removal of unapproved diagnostic
fields. Windows native lock and GUI execution require the next platform matrix;
this record does not claim a Windows installer or private Drive round trip.

No existing runtime, protocol, private host, Drive tree or TB3 service was changed.
Rollback is reverting the support commit; no private deployment rollback applies.
