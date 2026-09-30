# Unreleased fixed exchange layout

RP-009 design contract under the current owner-approved
[available takeover amendment](implementation-plan/revisions/R2/amendments/RP-008/A-002-available-owner-takeover.md).
Machine specification: `protocol/drafts/r2-exchange-layout.json`.
Pure structural validator: `src/tb4/exchange_layout.py`.
This does not release protocol v2 or replace the existing v1 adapter/tree.

## One authority, bounded records and exact identities

Commissioning selects one existing private root, exact native document/tab and
domain identity. The document contains one closed canonical JSON record, with
layout version/revision, domain, selected capacity and a fixed record map. Its
identity persists through ordinary state changes, role takeover and capacity
expansion. Do not find current state by filename, display name or folder scan.

Logical slot IDs use fixed zero-padded indices, independent of computer names,
operation IDs, hostnames or current enrollment. A registry binds enrolled device
identities/aliases to target slots; a display-name change does not rename a slot.
Each slot contains generation, operation ID, retention classification and bounded
body. Business states/field ownership are defined in RP-010; the layout validator
does not authorize arbitrary body data or dispatch a command.

| Slots | Purpose and ownership boundary |
| --- | --- |
| global.leadership / force_request | Current owner, private computer name, heartbeat/epoch and bounded GUI takeover request under RP-008 |
| global.commissioning / settings / registry / summary | Controlled setup/reconfiguration, enrollment bindings and WATCHDOG summary; role validators enforce future RP-010 permissions |
| ingress.NNN | One common SUBMIT request contract, validated/routed by WATCHDOG; no direct legacy FETCH_BALL injection |
| target.NNN.catalogue / status | Bounded private capability/freshness and correlated status projection |
| target.NNN.work / result | One outstanding unconsumed operation per target; WATCHDOG routes, FETCHER claims/executes/publishes by stage-specific ownership |
| target.NNN.cancel / ack | Reserved common-ingress control records; correlated request/routing/response fields, separate from busy work capacity |
| artifact.NNN.input / output | Descriptors for two pre-existing raw byte objects per target; actual payload not inside the control document |
| history.NNN / quarantine.NNN | Finite consumed-operation summaries and preserved malformed/ambiguous evidence descriptors; never overwrite unread or unresolved material |

All submission/control is one documented helper interface addressing this same
authority. A status query reads the authoritative snapshot and consumes no ingress
slot. CANCEL and ACK use their reserved target records even if all work ingress
slots, work/result or history slots are full. A pending control record is not
overwritten by another ID: duplicate correlation and exact response/recycling are
RP-010/040/046 responsibilities. Shared CAS contention is still possible; this
layout prevents capacity starvation, not a promise of zero provider latency.

Slot generation is a nonnegative bounded integer. It never wraps or resets when
reusing a slot or changing enrollment. Reset/replacement needs a controlled
identity migration with retained evidence, not generation zero over old data.
The operation ID remains attached to every result/control until explicit verified
consumption; UNKNOWN, BUSY and UNREAD are not free space. These retention tags are
layout protection classes, not replacements for execution/publication states.

## Setup-selected capacity and byte budget

| Dimension | Default | Allowed range |
| --- | ---: | ---: |
| Target slots | 8 | 1–64 |
| Work ingress slots | 4 | 1–16 |
| History summary slots | 32 | 1–128 |
| Quarantine descriptors | 8 | 1–32 |

These are versioned product limits, not inferred home topology. A broader
BALLPARK inventory can contain unregistered/discovered devices; enrollment into
this exchange consumes the separately selected target capacity. An installation
must not advertise more executable slots than it has provisioned. A deployment
needing more than this bounded profile requires a later controlled contract
revision; silently creating a second authority is forbidden.

Each target also reserves one input and one output raw artifact object, giving
`1 + 2 * target_slots` physical exchange objects (one document plus raw slots),
excluding the already selected root. Normal command, discovery and history
traffic creates zero objects. Raw slots are reused only after correlated
consumption and verified generation/descriptor checks. Their proposed per-object
payload cap is 8 MiB; larger output handling must follow the later explicit
bounded-output policy, never silent truncation labelled complete. The archive
contains this compact specification, not generated payloads or large backups.

The document cap is **512 KiB of canonical UTF-8 JSON**, including all record
envelopes and escaping. The machine spec assigns exact per-slot byte budgets.
The 32 KiB fixed reserve covers global slots, header/keys/separators and margin.
The maximum product of the permitted capacities fits the cap; tests also fill
every maximum-capacity slot to its actual serialized byte budget. Unicode code
points, JSON escaping and raw payload size are not interchangeable counts.
Oversized bodies must use an available artifact descriptor or fail admission;
they cannot borrow the reserved cancel/ACK/ownership capacity.

Provider references checked 2026-09-30: Google lists a native-document limit of
[1.02 million characters](https://support.google.com/drive/answer/37603). The
smaller TB4 byte cap is a conservative product limit, not a benchmark of provider
throughput. [Docs API quotas](https://developers.google.com/workspace/docs/api/limits)
currently list 300 reads and 60 writes per minute per user/project, with larger
project-wide limits. Actual configured quotas may differ. Capacity is not a
promise that every target can write at peak rate simultaneously. RP-011/015/016
must budget aggregate polling, heartbeats, CAS retries, workload and control
reserve using actual authorized principals/quotas, with bounded backoff and
visible throttling. No paid quota change or new principal is created here.

## Admission and preservation

New work needs free common ingress, target work/result and artifact slots, and
reserved history space. Claim these together in the same authoritative transaction
under RP-010/015; the pure `admission` function reports capacity only and grants no
reservation or authorization. Snapshot-based capacity checks alone are not CAS.
Full history stops new admission until legitimately consumed retention can be
released. Full quarantine blocks the affected quarantine-producing action; do
not delete old ambiguous evidence to conceal exhaustion. Status/cancel/ACK stay
available through their dedicated paths. One busy target does not serialize
independent targets except for the shared provider transaction/rate budget.

Output and input descriptors bind raw exact object ID, record generation, operation,
size/hash and publication state in the authority. Raw bytes or file rename alone
cannot indicate a command result or elect a WATCHDOG. Readers reject a body/hash
mismatch and inspect the same operation; no fallback to guessed/latest artifacts.
Publication/recycling mechanics and ownership are later RP-010/015/047/049 gates.

## Interrupted commissioning, expansion and repair

Prepare exact logical slots and durable provisioning intentions in the protected
setup record before creating any object. Record each creation as NOT_STARTED,
UNKNOWN or CONFIRMED with verified exact binding. An absent receipt is an error,
not proof that nothing happened. UNKNOWN means inspect that same attempted create;
do not repeat it and create a duplicate document. Duplicate bound physical IDs,
same-name ambiguity or wrong identity stop activation. An all-confirmed binding
plan is merely ready for schema/content/access readback, not a completed install.

For expansion, prepare an unpublished capacity revision, preserve every existing
record byte-for-byte and only add empty slots. Provision/read back the newly
required raw objects under explicit setup authorization. Reload the current
authority and conditionally commit expansion at the SAME document identity,
preserving concurrent changes or retrying the plan from a fresh snapshot. Verify
the new schema, capacity/bindings and compatible client instructions before using
new slots. The pure `expand_document` function stages data only; it performs none
of those external steps and does not grant migration permission.

Shrinking, ID remapping, changing authority, resetting generations or removing
retained records requires a separate migration; the normal expansion function
rejects these operations. Before publication, discard only an unreferenced
candidate. After publication, do not roll back by restoring an older document:
make a new forward revision preserving live/unknown/unread records and epochs.
Missing live authority or artifact bindings are inspected, not auto-recreated.

The v1 `tree-blueprint.yaml` and `DRIVE_TREE.md` remain historical/current-v1
contracts for existing deployments. RP-019 implements commissioned fixed capacity;
RP-057 handles any separately authorized legacy migration. This design does not
modify a running installation, real private topology or credentials.
