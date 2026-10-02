# RP-026 amendment A-001: local network table and device-description assistance

Date: 2026-10-02. Authority: the owner's explicit response to the RP-026
network-authority proposal, recorded by RP-026-A001-0012/0013.
Ordinary public implementation and isolated tests remain authorized. This is not
a live deployment, migration, reset or network-reconfiguration authorization.

## Owner decision

The network table belongs in the default local installation folder; its location
can be changed in program settings. TB4 must work with other users' different
topologies. WATCHDOG automatically observes/checks the commissioned network and
reports devices that lack an adequate description. A separate repository-owned
device-description SKILL assists the owner in producing deterministic,
machine-readable information needed by TB4, helpers and other programs.

A stable-IP assignment is an optional fact/status, not mandatory router/host
configuration or a global activation condition. UNKNOWN or not assigned does not
block discovery, description, enrollment or coordination. Only a specific action
whose commissioned capability truly requires stable addressing can require a
fresh confirmed fact, and its diagnostic must identify that prerequisite.
Recording an address or an owner declaration never proves router assignment.
Per-user router procedures, real topology and credentials stay private; they
are not part of the public product contract.

This supersedes the unaccepted RP-026 provisioning deliverable and the unresolved
DHCP-first/managed-host-first choice in the immutable A001 proposal. None of
RP-026.C1-C4 was accepted before this amendment. No earlier accepted checkbox is
reinterpreted, and no network-provisioning feature is claimed implemented.

## Active deliverable and invariants

One protected, bounded local network table per installation, defaulting to a
private data leaf inside its installation folder. An explicit settings selection
can change the location. Validate native ownership/permissions, current directory
identity and exact expected table/configuration revisions before any write.
Never silently select another folder, repair an existing folder's permissions,
overwrite foreign data, or copy credentials to another installation. Relocation
stages and reads back the same table before changing the active local selection;
retain the previous validated location and inspect any uncertain boundary.

Use canonical versioned JSON with a closed schema, bounded records, sorted
encoding, duplicate-key rejection and fixed diagnostic codes. Bind each
description to stable catalogue identity, domain and installation, never mutable
IP/name. Observation facts, owner-approved description facts and enrollment/
execution authority remain separate. Include only typed fields TB4 can interpret:
device identity/alias, platform and role/capability declarations, supported
interfaces/transports and provenance/freshness. Unknown values are explicit.
No passwords, keys, resolver material, shell snippets, instruction URLs or
router-management procedure fields are allowed. Protected network observations
may contain local addresses; exported assistance/status uses an allowlist.

WATCHDOG refreshes observation facts and produces bounded missing/inadequate/
stale-description notices. It cannot invent an approved description from discovery
hints, treat a SKILL proposal as executable code, or infer authority from stable IP.
The deterministic helper renders, validates and stages a description proposal.
The owner approves an exact fresh revision through the local program. Existing
shared BALLPARK publication still requires the existing current-owner CAS and
instruction pin; a local description is not remote acceptance or FETCHER enrollment.

The additional SKILL's real instructions live in this repository. Installed
packages contain repository pointers only. One compatible repository revision
governs an in-flight workflow; data cannot nominate an instruction source. The
development profile remains UNRELEASED until its separate release gates pass.

## Checks and dependent handoff

- RP-026.C1: qualify the closed deterministic table/description/status contract,
  including optional stable-IP facts and action-specific prerequisites.
- RP-026.C2: qualify installation-default/custom location selection, native
  protected persistence, restart and revision/readback-safe relocation.
- RP-026.C3: qualify observation-only notices and repository SKILL/helper/local
  approval integration, preserving identity/enrollment/shared authority.
- RP-026.C4: qualify missing/stale/inadequate descriptions, DHCP/name/address
  drift, ambiguity, malformed/duplicate/secret/instruction data, denied storage,
  conflicting writers and interrupted relocation. A missing stable IP alone
  must not block otherwise eligible work.

RP-027 consumes the table's staged location/configuration transaction and retains
unknown work; RP-029 consumes versioned owner-approved description updates and
address drift; RP-051 consumes the repository instruction/helper binding.
Their unaccepted definitions/mappings are linked to this amendment. Preserve the
RP-008 stale-owner takeover correction: no incumbent/all-sink acknowledgement
barrier is introduced by table maintenance. Paused instances cannot publish as
the active WATCHDOG.

## Historical RP-026 definition (unaccepted, preserved verbatim below)

# RP-026 - Authorized stable-IP provisioning adapter

Status, dependencies and requirement links: `../manifest.yaml`. [Mandatory work contract](../../../../development/WORK_INSTRUCTION.md) applies, including implementation authorization, per-check evidence and interruption handling. Checkboxes are a manifest projection.

**Deliverable / handoff:** A tested adapter for a deliberately selected network-management authority, plus unsupported-mode behavior.

**Inputs to inspect:** RP-005 network capability schema; RP-006 resolver; selected authority during commissioning. Historical runtime values are not current facts. New artifacts below are planned, not already implemented.

## Checklist

- [ ] **RP-026.C1** - Choose a supported DHCP/router or managed-host authority from commissioned facts and explicit authorization, not a hardcoded vendor/address.
- [ ] **RP-026.C2** - Read current reservations/configuration, detect conflicts and compute a reversible minimal change binding the intended stable identity.
- [ ] **RP-026.C3** - Apply only an approved change through the adapter; verify the actual assignment and retain private rollback data without logging credentials/topology publicly.
- [ ] **RP-026.C4** - Test unsupported management access, address conflicts, changed identity, lost authorization and failed readback; report NOT_PROVISIONED instead of an invented fixed IP.

**Acceptance / records:** All four checks and the common work-contract gates must pass. Store per-check evidence in `../evidence/RP-026/Axxx/` and INTENT/OUTCOME events in `docs/development/journal/RP-026/Axxx/`; update the manifest and RESUME before proceeding.

**Rollback / unresolved action:** Restore the exact prior reservation/configuration through the same authority after safe checks; no second DHCP server or blanket subnet edits.
