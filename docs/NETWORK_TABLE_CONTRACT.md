# Protected local network table and device descriptions

Owner authority: implementation-plan/revisions/R2/amendments/RP-026/A-001-local-network-table.md.
This is public development; the R2 instruction profile remains UNRELEASED.
WATCHDOG checks the commissioned topology and reports description needs. It does
not automatically assign IPs, rename hosts, change DNS or configure a router.

## Local location and protection

An installed WATCHDOG uses its actual executable installation folder's
network-table leaf by default. Development runs supply an explicit
--installation-root; no current working directory or developer machine is a
product assumption. The local settings window offers another private folder.
No data is created merely by opening that window. An owner saves the selected
location after a shared domain identity is commissioned. Empty discovery is valid.

The selected path/table UUID/domain/native directory binding and exact pending
operation are protected in the existing setup frame. The table's own fixed native
settings.json frame contains the NETWORK_TABLE payload; settings.pending and
settings.lock are bounded staging/locking objects, not per-device files.
Never parse the native frame as a naked table: LocalNetworkTable verifies
principal/host/directory binding, digest, revision and protected permissions.
Changing location creates a new private leaf, stages the same exact payload,
reads it back, then changes the active selection. The old leaf/data remains.

CREATE/MOVE/UPDATE is recorded before native mutation. Exact completed or staged
candidates can be inspected after interruption; an existing empty/foreign
destination cannot be overwritten or adopted. Conflicting source revisions or
readback failures retain the selection/pending intent. Explicit completion of the
same local change follows an exact current-state inspection, never blind replay.
No chmod/ACL repair, credential copying, identity reset or remote storage
migration occurs. Linux installers refuse replacement/removal if a default table
still resides in the installation folder; move it through settings first.
Windows uninstallation does not track or delete user-created table files.
Installer preservation and platform constraints require their own qualified tests.

## Machine interface

protocol/network-table-v1.schema.json defines the closed, bounded table format.
protocol/network-description-v1.schema.json defines one owner proposal.
src/tb4/network_table.py supplies stricter semantic checks: canonical UUID/IPs,
unique catalogue identities/aliases/endpoints, domain/installation binding,
role/launch consistency, supported provenance and freshness. Consumers use
validate/parse_table/render_table, rather than accepting JSON Schema alone.
Encoding is sorted ASCII JSON with no NaN or duplicate keys. PrivateSettings adds
the native protected frame; render_table is for protected consumers only.

Descriptions have typed device kind, platform, TB4 role declarations, launch
modes, transports, capability declarations and optional stable-IP status.
No arbitrary script, router procedure, credential, instruction URL or path is
allowed in a proposal. Discovery observations remain separate private facts.
Missing/inadequate/stale descriptions generate notices with opaque identities,
aliases, field names and optional addressing provenance/freshness only.
Helpers use the same schema and revision, not inferred prose. Unknown capability
declarations are truthful, not execution grants. Non-computer devices need no TB4
role; a declared TB4 role requires known platform and architecture for adequacy.

A DHCP/name/address change does not retarget a description. Stable-IP facts are
bound to the exact current endpoints; drift expires that fact. An owner-reported
assignment is labeled OWNER_DECLARATION, not verified network provisioning.
Unknown/not-assigned addressing never blocks otherwise eligible discovery,
description or enrollment. addressing_prerequisite checks only an explicitly
required addressing prerequisite: fresh ASSIGNED from a trusted read-only
FIXED_HELPER fact for the same endpoints. SATISFIED is not work authorization.
No provider-specific status adapter or home network fact is invented here.

## Assistance and approval

The repository-owned skill/tb4/operations/device-description/SKILL.md uses
DescriptionAssistant.begin/propose/confirm. The host supplies its current
compatible repository adapter/runtime facts; the helper pins and verifies the
guidance/schema closure, formats one identity/revision-bound proposal and requires
exact digest approval. A local Qt editor provides direct owner declarations.
Approval updates the local table only, not FETCHER enrollment, authenticated
capabilities or shared BALLPARK. Remote publication uses the existing owner CAS.
Untrusted descriptions/observations cannot select instructions or confer authority.
Installed tb4-describe-device is a repository pointer only; no installed manual
or runtime activation is created by this development change.

RP-027 consumes location/configuration maintenance and unresolved transactions.
RP-029 consumes revision/provenance/drift; RP-051 consumes the tested host helper
binding. These future acceptance gates are not completed by this contract.

