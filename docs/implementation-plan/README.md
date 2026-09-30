# TB4 Implementation Plan

## Active revision

Read [CURRENT.yaml](CURRENT.yaml) first. It selects the current development plan,
status authority, checklist, work instruction and resume cursor.

The active realignment plan is [R2](revisions/R2/README.md). Its RP-001..RP-064
steps have their own manifest, checks, evidence, attempts and amendments. R2 is a
planning revision, not a released software/protocol version. The latest owner
request authorized planning only; do not start implementation from a checkbox.

## Historical IP plan

The existing `manifest.yaml` and `steps/IP-XX-*.md` retain the chronological
IP-01..IP-70 history unchanged. Only that manifest is status authority for IP IDs.
Do not copy its VERIFIED statuses to RP IDs or treat old acceptance as proof of
new realignment requirements. Its current_step is historical, not the active
work selector when CURRENT.yaml points to R2.

## Shared status and isolation rules

Allowed step statuses remain PLANNED, IN_PROGRESS, VERIFIED, BLOCKED and
SUPERSEDED. VERIFIED requires objective reviewed evidence for the exact scope;
BLOCKED is not completion, and a defect can reopen accepted work for revalidation.
Do not silently rewrite accepted meanings; use isolated amendments.

Legacy records use `steps/IP-XX-*`, `amendments/IP-XX/`, `evidence/IP-XX/`.
R2 records use `revisions/R2/steps/RP-XXX.md`, `revisions/R2/amendments/RP-XXX/`,
`revisions/R2/evidence/RP-XXX/Axxx/` and the mandatory development journal.

Follow [WORK_INSTRUCTION.md](../development/WORK_INSTRUCTION.md). Complete work
in numeric order subject to explicit dependencies and recorded scheduling
exceptions for truly independent work. Publish pre-action intent and verified
outcome checkpoints; do not rely on conversational memory for interrupted work.

## Historical step 1

IP-01 records creation of the TB4 execution contract; original engineering work
started at IP-02. Preserve this history rather than renumbering it during R2.
