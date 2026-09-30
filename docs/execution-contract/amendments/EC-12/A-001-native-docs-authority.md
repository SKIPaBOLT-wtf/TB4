# EC-12 A-001: authoritative state and body in one native Docs transaction

Later owner correction: [EC-16 A-001](../EC-16/A-001-available-watchdog-takeover.md)
removes the all-sink takeover barrier mentioned below; strict shared-record
transactions and readback remain required.

Date: 2026-09-30. Point: EC-12; EC-16 and EC-30 remain binding.
Approval: owner approved RP-008 candidate 3 design/prototypes, recorded in
RP-008-A001-0016. Review/qualification state: active R2 manifest and A002 evidence.

Problem: raw Drive rename plus body writes are not one conditional transaction.
Old interpretation: the EC-12 rename/readback/body example describes current v1
object state. New interpretation for the owner-approved future Google mode:
authoritative logical state and body live in one fixed native document and are
conditionally committed together. Read, validate ownership/identity/epoch,
strict-revision mutation and authoritative readback remain mandatory. Raw file
names/projections are not authoritative in this mode. Local/external effects
still require their own epoch admission and takeover drain barriers.

Reason, compatibility boundaries, exact mechanism and affected RP steps are in
[RP-008 A-001](../../../implementation-plan/revisions/R2/amendments/RP-008/A-001-native-docs-authority.md).
No historical v1 acceptance is rewritten. This is a design amendment, not live
migration permission or proof that the runtime adapter/gateways already exist.
