# EC-16 A-001: available WATCHDOG takeover and precise fencing scope

Date: 2026-09-30. Point: EC-16. Owner approval: explicit correction recorded in
RP-008-A002-0013; current implementation intent RP-008-A003-0001.

Problem: requiring every old execution sink to acknowledge/finish before a new
WATCHDOG activates prevents takeover when a machine powers off or is unreachable.
Old interpretation: no new active coordinator until all old protected effects
are fenced and drained. New interpretation: a stale authoritative record permits
immediate conditional owner/epoch replacement; forced GUI requests also permit
takeover without old-host acknowledgement. Shared records use strict atomic
revision/owner/epoch checks. Before new external dispatch, actors cooperatively
refresh ownership. Already dispatched effects may remain uncertain or overlap;
preserve their correlated state without blocking the entire coordination role.

Reason: owner's explicit availability priority. Compatibility: future selected
native-document mode only; no silent v1 migration, weaker unconditional writes or
new device-action permissions. Affected RP-008/009/010/011/012/015/016/017/018/019,
network/execution paths, RP-053 GUI and RP-058/060/063/064 acceptance are specified
in [RP-008 A-002](../../../implementation-plan/revisions/R2/amendments/RP-008/A-002-available-owner-takeover.md).
Review state: current R2 manifest/A003 evidence, not a runtime completion claim.
