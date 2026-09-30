# R2 security and failure decision gate

RP-012, UNRELEASED. This reviewed specification does not activate R2, migrate a
deployment or qualify a real principal, credential store, OS, launcher or topology.
The installed v1 contract remains unchanged. The executable policy is
`src/tb4/security_contract.py`; its exact export is
`protocol/drafts/r2-security-matrix.json`. Existing [security](SECURITY.md),
[failure recovery](FAILURE_RECOVERY.md), [command](COMMAND_CONTRACT.md),
[exchange layout](EXCHANGE_LAYOUT_CONTRACT.md) and [timing](TIMING_CONTRACT.md)
contracts supply the boundaries below.

## Authorization and roles

The one native Docs authority is private to authorized cooperative principals.
Its ACL grants document access, not per-field isolation. Revision CAS, payload
hashes, owner epochs, operation identities and deadlines protect integrity and
race handling; none authenticates an arbitrary editor. A compromised authorized
editor can potentially request target execution under the existing security
model. Untrusted editors cannot share this authority safely. Commissioning must
verify actual account/ACL identity and disclose this trust boundary; an unknown
or compromised ACL blocks mutation until access is reviewed. Do not claim that
logical roles contain a malicious document editor.

The LLM supplies an authorized objective and reads verified results. Deterministic
COACH helpers validate and admit requests, cancellation and explicit result
consumption. LLM text and result text cannot manufacture a permission. WATCHDOG
owns coordination and commissioned fixed launch/network capabilities, never the
workload process. FETCHER independently checks enrolled domain/target, operation,
generation, payload hash/size, deadline, instruction compatibility and durable
execution identity before claiming work. RUNNER supervises the particular local
process under its configured least-privileged identity. A fixed SSH/OS/external
helper accepts only commissioned typed operations; no arbitrary shell command,
implicit elevation or fallback to a different account. Credential resolution is
local, purpose-bound and never serialized into control objects. Co-location does
not combine role permissions or activity clocks.

The matrix lists every action, allowed actor and required predicate. Unknown
actions, actors, predicate names or non-boolean values reject. Missing or false
required predicates deny. These are executable design predicates over already
verified inputs, **not runtime authorization**: callers cannot supply `True` to
obtain credentials or execution permission. The actual adapters must establish
the predicates, preserve immutable target/payload bindings, and enforce the
same boundaries before each operation. Identity replacement/reset requires a
separate exact owner-authorized setup operation; ordinary ingress cannot do it.

## Available takeover and uncertain effects

A standby may claim a stale owner by a fresh strict conditional write. The first
successful CAS becomes active immediately; no old-owner response or sink ACK is
required. A GUI takeover request identifies a unique requester installation and
its display name. The incumbent checks the owner and request before new shared
writes or external dispatch; the requesting installation may atomically consume
its matching request. Display names are informational, never authority keys.
The binding [owner amendment](implementation-plan/revisions/R2/amendments/RP-008/A-002-available-owner-takeover.md)
governs expiry, clock qualification and request races.

Already-dispatched external effects may overlap a takeover. Neither a document
write nor this policy atomically revokes a process or network packet. Preserve
each uncertain operation and reconcile its same execution; do not replay it or
wait for all targets before serving independent work. Cancellation is a request,
not evidence that interruption occurred. Missing publication is not evidence of
no effects. Result retention requires exact verified result and explicit
consumption; timeout, offline owner, stale name or new coordinator cannot recycle
unknown or unread work.

## Fault scope and response

The exported fault table is closed and returns a bounded reason, scope and next
action. Every row preserves evidence and prohibits automatic clear/replay.

| Scope | Examples | Required response |
| --- | --- | --- |
| Operation | nonzero exit, partial effects, cancellation, unknown execution, stale result, malformed ingress, output overflow | Preserve exact identity and execution/capture evidence; reject stale data; correlate a bounded rejection; reconcile without rerun. |
| Target | host offline, target credential missing, SSH identity changed, runner permission denied | Block only the missing capability. Keep a valid polling route when launch is unavailable. No implicit elevation or identity acceptance. |
| Transport | authority credential unavailable, provider outage, rate limit, lost write reply | Retain durable local outbox, stop unqualified shared mutations, bounded retries of reads/known idempotent work. Inspect the same ambiguous transition before retrying. Local process supervision continues. |
| Capability | clock confidence insufficient | Block only the time-dependent decision lacking proof. The RP-008 bounded unchanged-heartbeat takeover proof remains available when qualified. |
| Coordinator | owner superseded | Demote before new dispatch; preserve already-running target work and its result. |
| Domain | ambiguous authority identity, corrupt authority body, compromised access | Preserve evidence, block mutation, report recovery needed. Never silently recreate a root/document or erase the invalid body. |

## Input, media, output, rate and logging limits

Control input is UTF-8 JSON, at most 512 KiB before parsing. Reject duplicate
keys, invalid UTF-8, unpaired surrogates, nonfinite numbers including exponent
overflow, non-object root, trailing data, depth over 32 or more than 50,000 nodes
(keys count). Parse success is not business schema or authorization validation.
Adapters must bound raw media before allocation/decompression and schema-check
the entire authority under one observed revision; a partial parse cannot authorize
work. Strict CAS uses the fresh same-principal revision, never a cached or
cross-account revision. RP-015/016 must qualify this against the actual provider.

Artifact descriptors have closed fields and exact operation binding, enrolled
indexed slot 000..063, byte size, SHA-256 and completed-publication state. The
slot must also match the protected enrolled mapping; the index range alone is
not enrollment. R2 raw artifacts are at most 8 MiB. Input must be nonempty and
match the admitted payload hash, allowlisted interpreter and fixed suffix.
Download only the exact provisioned object, never an untrusted URL, path or
filename; reject redirects/alternate objects unless the provider adapter proves
the same authenticated object identity. Verify before execution. A local basename
is derived from the binding hash and fixed suffix. Actual private temporary file
creation, no-follow/reparse-point protection, permissions, race-free open/use,
cleanup and same-user tampering limits require native qualification. This pure
model performs no filesystem or network IO and proves none of those properties.
Output descriptors cannot select an interpreter and are always data.

RP-010 compact tails are bounded to 128 characters, control status to its RP-009
512-byte record budget, and the design result-view wrapper to 512 UTF-8 bytes.
The latter labels untrusted data; it is not a sanitizer or prompt-injection cure.
Result text cannot override pinned operational instructions, authorize a new
action, open a URL automatically, reveal a credential, or change the plan. Keep
instruction/result provenance separate in the actual helper and SKILL flows.
Truncation/overflow must preserve explicit capture completeness, exit and effects
evidence. Bounded capture must continue draining/supervising a noisy child, or
stop it under an explicitly declared limit policy; never deadlock or fabricate a
complete result. RP-047/048/049 must settle and prove this before acceptance; if
the accepted RP-010 wire schema needs another field, publish a versioned amendment
and revalidate consumers before activation. Do not silently broaden the schema.

Use the RP-011 timing/quota profile and reserved control capacity. Average request
budgets are not burst, starvation or adversarial-ingress proofs. RP-015/016/058
must enforce bounded retry/backoff/queue limits, fairness, deadline handling and
control headroom under provider rate limits, contention and reconnect storms.
Do not shorten owner-set polling intervals to conceal an unsupported profile.

Logs use allowlisted reason codes and necessary opaque correlation identities,
bounded record sizes and rotation. No raw provider exceptions, credential values,
private target/root mappings, command bodies or output in public development
logs. Arbitrary workload output may contain secrets: a size cap, hash or wrapper
does not make it public-safe. Store authorized private results under protected
deployment permissions; public evidence uses reviewed synthetic data only.
Private detailed diagnostics require explicit local scope and redaction before
export. RP-047/059 must prove concrete caps, redaction and rotation in packaged
paths; this matrix deliberately does not claim an implemented log subsystem.

## Supported mode inventory and mandatory acceptance blockers

The machine-readable dimensions cover native Docs authority, legacy raw Drive,
synced files and memory fixtures; Windows/Linux/other OS; same/separate hosts;
no launcher, fixed SSH/OS/external launcher; desktop/service/headless sessions;
cooperative/untrusted editor; authorized/hostile workload; commissioned wake and
scoped network-change capability. All 4,608 combinations are reviewed by fixtures.

Native Docs is the selected R2 authority. Legacy raw Drive, synced folders and
memory models are not alternative R2 production authorities; no implicit fallback
is allowed. Windows and Linux remain required. Other OS support is unqualified.
Least privilege is not a hostile-code sandbox; executing owner-authorized code
can affect all resources accessible to its process identity. Supporting hostile
workloads or untrusted editors requires a separately approved architecture, not
a checkbox in this matrix.

Every `evidence_gates` entry in the export identifies mandatory downstream step
owners. All are **NOT_QUALIFIED by this design**. The common gates cover native
CAS, cooperative role enforcement, private ACL, durable unknown/output handling,
bounded parsing/media/rates, instruction/result provenance and final packaged/live
authorization. Selected modes additionally require their OS credential/process
proof, same/separate-host acceptance, launcher or no-launcher idle behavior,
service/headless session, wake topology and network-change qualification.
Failure of one optional commissioned capability must be visible and scoped, but
it cannot silently waive an essential promised product requirement.

`mode_policy` returns missing gates and unsupported reasons. Even a hypothetical
set containing every gate name returns `runtime_activation=false` and
`release_authorization=false`: it does not read or verify evidence. Actual named
native/provider/package/topology tests and scoped owner live authorization remain
mandatory. RP-059/060/061/064 must consume this inventory, refuse missing proofs
for a selected mode, and carry unresolved required-product modes as acceptance
blockers. A passing RP-012 means the matrix and its adversarial specification were
reviewed; it is not a claim that the product passes those later gates.

Rollback keeps unknown work, exact identities and deny-by-default boundaries.
Disabling an unqualified capability must report it unavailable; no silent switch
to v1 writes, unrestricted SSH, broader credentials or replay is allowed.
