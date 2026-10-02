# RP-027 amendment A-002: inherited effect evidence and local admission reservation

Date: 2026-10-02. Authority: existing public implementation authorization,
RP-027.C1 and A-001. This implements its inherited-operation gap within the same
authority. No accepted checkbox, installed protocol, deployment, migration,
router configuration, reset or unknown-effect replay is authorized or reinterpreted.

The existing global.summary slot reserves the closed optional tb4_effects_v1 journal.
It carries bounded per-action exact operation/owner/epoch outcomes and a maintenance
barrier. It is evidence, not a second control plane or execution grant. Unrelated
summary data is retained unchanged. The guarded slot can only change through the
dedicated evidence primitive; ordinary record publication must preserve its whole
row. Bootstrap refuses occupied BUSY/UNREAD/UNKNOWN summary work rather than
repurposing or concealing it. Guard-aware summary evolution is subsequent work;
this unit never discards a prior non-effect summary payload or unread state.
The independent slot generation never rewinds workload generations. Closed effect
and native-checkpoint schemas are pinned only under UNRELEASED; no build is granted.
The existing unreleased maintenance WAL schema allows a covered adopter's explicit
RESOLVED certificate; its pending field remains null. Actual shared coverage and
fresh zero-blocker checks are mandatory code prerequisites, not JSON grants.

A protected native checkpoint reservation fences new local work before inspecting
maintenance. An already admitted call has durable UNKNOWN evidence before any
invocation. A late actual reply preserves the reservation; native conflicts fail
closed. The runtime journals UNKNOWN in the sole existing authority before bounded
work, and records terminal evidence only for that exact operation and current
owner. An uncertain journal mutation is inspected at the same identity after
restart; local pending promotion cannot resend it or invoke external work.

Initial coverage can be created only by the initial epoch-one current owner from
its exact protected checkpoint. A later owner cannot manufacture coverage of old
unjournaled effects from an empty local installation. Legacy marker-absent behavior
remains compatible; this evidence limit applies to routing reconfiguration and
requires a separately reviewed migration/evidence procedure for an existing later
epoch deployment. No live migration is attempted by this amendment.

Maintenance publication atomically records the marker and original local unresolved
status. A fresh owner may adopt without any old-machine/all-peer/all-sink contact.
Covered, unchanged, zero-blocker shared evidence allows explicit current-owner
resolution while the original machine is unavailable. UNKNOWN shared effects/work
or an uncleared original local evidence barrier remain unresolved. Only the original
guarded owner may refresh its local-clear evidence after fresh actual local checks;
this does not erase shared UNKNOWN work or substitute a checkbox for cancellation.

Leadership renewal and the first successful strict-CAS stale takeover remain
independent of maintenance/evidence eligibility. Computer labels are display data.
The amendment creates no peer acknowledgement barrier, host-specific assumption,
credential disclosure or automatic retry of an uncertain effect.

C1 acceptance still requires actual native/race/crash/fallback/negative regressions.
C2 candidate, C3 same-object relocation and C4 monotonic publication/admission,
plus full platform/common/review gates, remain separately required.
