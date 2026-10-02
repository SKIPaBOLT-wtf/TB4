# R2 - TB4 realignment implementation plan

Planning checkpoint: 2026-09-30. Baseline: `3d3e6e0dc0eee51e694e83b37547c047cea8e355`.
**64 executable steps, 256 independently identified checks.**
Current authority: [implementation authorization](IMPLEMENTATION_AUTHORIZATION.md).
The manifest records accepted progress; the original planning checkpoint remains historical.
R2 is a planning revision, not a claim that software/protocol version 2 is released.

## Start here

Read [OWNER_ADDENDUM.md](OWNER_ADDENDUM.md), [WORK_INSTRUCTION.md](../../../development/WORK_INSTRUCTION.md),
[manifest.yaml](manifest.yaml), [CHECKLIST.md](CHECKLIST.md), then the indicated
step and its latest attempt. [requirements.yaml](requirements.yaml) maps all 22
requirement groups to steps. [defects.yaml](defects.yaml) carries unresolved pilot
symptoms. [PORTABILITY_AND_PRIVACY.md](PORTABILITY_AND_PRIVACY.md) defines the
cross-system/privacy acceptance axes. Use the current [resume cursor](../../../development/RESUME.yaml).

## Relationship to existing work

The latest owner-approved [RP-008 takeover amendment](amendments/RP-008/A-002-available-owner-takeover.md)
selects immediate conditional takeover of stale ownership and a forced GUI request,
without waiting for all execution sinks. It supersedes the earlier global barrier
while retaining one native Docs authority. Acceptance remains in the manifest;
live migration remains separately gated.

The original IP manifest and evidence are retained unchanged as historical scope.
New RP IDs deliberately do not overwrite, renumber or falsely re-VERIFY those
steps. CURRENT.yaml selects this active revision. Each RP has an isolated
specification, attempt journal, evidence and amendment location; the existing
39-point execution contract still applies unless a later explicit amendment says
otherwise. Existing code is reused/adapted after current inspection, not rebuilt
without evidence. Original IP-68 failures remain unresolved acceptance input.

The earlier instruction to stop before detailed planning was satisfied and is
superseded only by the owner's new authorization to plan. Planning completion
is not authorization to start implementation, a live pilot, new installation,
network configuration or shared-state recovery. The later explicit [implementation authorization](IMPLEMENTATION_AUTHORIZATION.md)
supersedes that wait for ordinary public development only.

## Work and status rules

The manifest is the sole status/check authority for RP IDs. Per-step checkboxes
and the index are projections and must be updated with the same evidence-backed
checkpoint; do not tick them independently. Initial statuses are all PLANNED,
completed_checks/evidence are empty, active_attempt is null. No work is labeled
VERIFIED because this plan exists.

Use numeric order with explicit dependencies. An earlier unresolved technical
choice may block a later capability; a recorded schedule exception may proceed
only with demonstrably independent work, not bypass an unmet prerequisite.
The first three steps implement enforcement/resume/debug tooling. Until then,
the same mandatory checkpoint process is performed manually.

Design decisions are deliverables with acceptance evidence, not assumptions to
silently choose during coding. Key decision gates: RP-008 (safe storage/leadership),
RP-009 (fixed capacity/layout), RP-010/011 (schema/timing), RP-026 (protected local network table and device-description workflow), RP-042 (actual exit-mode launcher). Blocking a required
feature or declaring it unsupported does not satisfy that feature's final gate.

## Completion rules

Every check needs exact source/procedure, expected/observed result, failure cases,
platform/topology scope, reviewed sanitized evidence and an interruption/rollback
boundary. All four checks plus the common work-instruction gates are required for
step VERIFIED. A defect opens a new attempt and forces scoped revalidation; it
does not delete earlier evidence. No live commands were sent to create this plan.

The owner's [RP-026 local-network-table amendment](amendments/RP-026/A-001-local-network-table.md) supersedes the unaccepted stable-IP provisioning requirement. WATCHDOG observes topology and reports description needs; stable addressing is optional informational status, with concrete action-specific prerequisites only.
