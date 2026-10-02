# RP-027 amendment A-001: staged changes within the existing authority

Date: 2026-10-02. Authority: public implementation authorization and the existing
RP-027 definition, with the owner's RP-008 available-owner takeover decision and
RP-026 installation-local network-table direction. This narrows implementation
boundaries and adds an optional unreleased marker; it grants no live operation,
deployment, migration, router change, reset or workload replay. No RP-027 check
has been accepted and no earlier accepted checkbox is reinterpreted.

RP-027 uses the same installation/domain/backend/layout and sole authority. A root
location change must preserve and rebind the existing fixed objects; creation of
a replacement control authority is outside this step. Topology/launcher/table
location and credential-reference changes are protected local candidates, subject
to actual first-run prerequisites, current-owner admission and exact readback.
Stable-IP assignment remains optional unless a concrete action needs that fact.

The existing global.settings budget gains the closed optional configuration-v1
marker in the UNRELEASED profile. Marker absence preserves legacy compatibility.
The marker gates ordinary dispatch/writes during maintenance and binds new work
to a freshly inspected local configuration revision. It does not establish that
external work stopped. Elections, heartbeats and first-CAS stale takeover continue
without incumbent/all-peer/all-sink acknowledgement barriers.

Canonical workflow: [RECONFIGURATION_CONTRACT](../../../../../RECONFIGURATION_CONTRACT.md).
RP-027.C1 still requires maintenance entry, evidence preservation and explicit
same-operation resolution; C2 requires a staged first-run-validated candidate
without early promotion; C3 requires actual adapter coverage for same-object root
relocation, fallback, access loss and interrupted commit; C4 requires monotonic
descriptor/configuration publication, stale-admission refusal and preserved work.
Source foundations or passing isolated tests alone are not check acceptance.

Protocol changes affect only future qualified builds. The installed pointer/profile
is untouched and the catalog remains UNRELEASED with no authorized production build.
