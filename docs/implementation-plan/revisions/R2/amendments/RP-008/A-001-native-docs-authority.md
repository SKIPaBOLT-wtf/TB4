# RP-008 amendment A-001: one native Docs control authority

**Later owner correction:** [A-002](A-002-available-owner-takeover.md) supersedes
the all-sink activation barrier and zero-overlap external-effect requirement below.
The native-document authority remains selected. This text retains the earlier
design reasoning; follow A-002 for current takeover semantics.

Date: 2026-09-30. Approval: owner explicitly approved candidate 3 in the active
session; recorded in RP-008-A001-0016. Design/prototype authorization only.
Review/acceptance: RP-008 A002 evidence and manifest, not this approval sentence.

## Problem, old interpretation and new interpretation

The raw Google Drive adapter checks versions before unconditional writes. That
cannot provide shared leadership exclusion or prevent a suspended old actor from
overwriting a new actor. A001 contains both actual-adapter counterexamples and an
isolated real Docs required-revision experiment. A CAS lease beside independently
mutable authoritative files still leaves a split transaction.

For the selected Google mode, use ONE fixed native Google Docs document as the
sole authoritative control record in the same commissioned TB4 domain. Leadership,
ingress, ownership, command state and terminal publication become bounded records
inside that document, updated under strict requiredRevisionId. Existing logical
vocabulary and identity/correlation semantics remain; a raw filename is no longer
the authoritative command state. Raw reusable artifact slots may carry payload
bytes, but only a committed document descriptor/hash/generation authorizes their
use. Optional file projections are explicitly nonauthoritative and cannot elect,
dispatch, acknowledge, recycle or override the document.

This selects a design mechanism, not a deployed implementation. No protocol-v1
file, accepted historical check, installer, existing domain or installed SKILL is
silently migrated. There is no second coordination service or second TB4 domain.

## Concrete authority transaction

Commissioning binds domain identity, exact document identity, fixed tab identity,
schema/protocol revision, enrolled principals and finite capacity in protected
configuration. Never discover an authority by same-name search or make a second
document when reads fail. Initial creation requires commissioning authority and
is reconciled by exact created identity after a lost reply. Activation requires
verified access and resolution of any previous authority/in-flight operations.

The qualified adapter reads the configured tab plus that caller's current opaque
Docs revision in one document read. It validates one closed machine record and
its bounds; malformed/human-edited/unsupported content stops mutation and preserves
evidence. The adapter constructs ONE atomic batch replacing that bounded record,
with writeControl.requiredRevisionId from that exact observation. Deletion and
insertion ranges must use Docs UTF-16 indexing, the commissioned tab and its
terminal newline rules. targetRevisionId merging and unconditional retry are
forbidden. Native rich-text styling is not part of the control record contract.

Each transition validates role ownership, domain, current epoch, operation ID,
record generation, expected state and revision before constructing the request.
All normal clients obey this contract; Docs file ACLs do not themselves enforce
TB4 field-level roles. A malicious editor with unrestricted document write access
is outside the crash/partition threat model and is a commissioning/security risk
to address explicitly in RP-012/020/021. Credentials never enter this document.

A rejected revision means reload/revalidate the SAME operation, not rerun a job.
An ambiguous response means inspect its durable operation/transition identity;
confirmed applied, confirmed superseded, or UNKNOWN remain distinct. No dependent
action before authoritative readback. Revisions are user-specific opaque tokens,
not epochs or timestamps; each principal reads its own. Expired/invalid tokens
cause a fresh read, never weaker writes. Future adapter tests must inspect actual
request bodies and wrong/stale revisions, not just a mock interface flag.

## Epoch arbitration without an assumed server clock

The document stores monotonically increasing leadership epoch, owner enrollment,
phase and progress/heartbeat sequence. An existing valid incumbent is preferred;
newcomers remain PAUSED/OLDER_DOG_DETECTED. They may read ownership, but perform
none of the incumbent's protected network/maintenance/publication work.

After a bounded local monotonic observation window with no incumbent progress,
a candidate may CAS the SAME unchanged authority observation to the next epoch
in ACTIVATING. A fresh incumbent heartbeat invalidates the contender's revision.
Clock discontinuity, unavailable authority or insufficient observation stops the
attempt. Suspicion is not proof of death: asynchronous delay can cause false
suspicion. Safety comes from revision exclusion and sink barriers, not clock
accuracy. Timing/failure-detector policy is specified in RP-011/016; no inferred
provider wall-clock lease is introduced. Healthy progress observed within that
qualified window retains incumbency. No scheduler can promise perfect failure
detection under unbounded delays.

Concurrent CAS contenders have one winner per revision. A paused or partitioned
candidate cannot become ACTIVE from cached state. An ACTIVATING owner also emits
progress; a stalled activation can be replaced by a higher epoch through the same
observation/CAS process. Epochs never decrease through restart or rollback.

## Every protected effect needs an actual sink barrier

A document epoch cannot revoke a process's existing OS/network privileges. All
protected effects must be mediated by an enrolled local/destination gateway that
authenticates authority/grant and caller, keeps a durable maximum accepted epoch,
and serializes fence advancement with effect admission. This is a TB4 execution
helper on the relevant host, not a second control-plane authority. It stores only
its local fence/operation outcomes; election and authoritative shared state remain
in the one document. WATCHDOG coordinates; FETCHER/helpers execute effects.

The candidate remains ACTIVATING while contacting every enrolled protected sink
in the fixed authority record. Each sink first durably raises its epoch floor,
refusing further old starts, then drains previously admitted effects. It returns
an authenticated, domain/target/owner/epoch-bound receipt only after every older
effect is completed with known outcome or termination plus containment is proved.
Started/unknown child or external actions are not a successful drain. Existing
operation identity and payload digest survive takeover; a duplicate returns its
record, and a different payload under the same identity is rejected.

All required receipts must be committed/rechecked against the SAME current epoch
before the document transitions to ACTIVE. Missing, duplicate, stale, wrong-domain
or wrong-target receipts fail activation. Old shared writes are already rejected
by CAS. A delayed old effect can still arrive during ACTIVATING before that sink
is fenced; it must be included in the drain. Once the new epoch is ACTIVE, every
old effect is finished/contained and every old new-start is refused. The design
does NOT claim instantaneous distributed revocation at the first CAS.

Each effect admission requires a fresh authoritative observation, an authenticated
request with the exact epoch and a local serialized admission check. Suspension
between the remote read and admission is safe because a completed takeover has
already advanced that same sink's durable floor. Cached old authorizations cannot
be reused as an unlimited offline execution permit. An unreachable authority
stops new admissions; already admitted execution is inspected, never blindly
replayed. Receipt authenticity, persistent epoch integrity and exclusive mediation
are mandatory implementation/qualification conditions, not properties supplied
by a plain Python dictionary or Docs CAS.

For routers, SSH, WOL and other nontransactional effects, all participating actors
must use the qualified gateway at the actual dispatch boundary. The gateway must
prove bounded completion/containment of previously submitted external effects;
an irreversible or ambiguously delayed external action holds activation until
resolved. Merely moving a read/check into a helper does not qualify it. Direct
legacy paths and bypass credentials are disabled before commissioning this mode.
Remote unreachability or lost durable gateway state leaves ACTIVATING/blocked,
never a fabricated safe ACTIVE. Automatic takeover is enabled where all required
capabilities qualify; unsupported capability is not final fallback acceptance.

## Proof scope and availability limits

`tools/experiments/docs_authority.py` models one atomic CAS record and an indivisible
durable admission/fence gate. The associated tests enumerate contender ordering,
four old-start suspension points, stale reads/fresh-read wrong owners, partition,
uncertain observation clock, interrupted activation, lost response inspection,
unfinished/unknown effects, deduplication and multiple required sinks. They prove
the stated state-machine invariant under those assumptions. A001 separately
verified Docs strict-revision writes on an isolated fixture that was then deleted.

The local model does not prove gateway crash durability, authentication, process
containment, remote-effect completion, provider throughput or filesystem locking.
Those are explicit later implementation/acceptance gates. Single-authority loss
or an unresolved old effect may sacrifice availability to preserve safety. No
unqualified shared-folder deployment is included: RP-018 must provide equivalent
atomic authority and sink semantics for a specific accessible storage mode.

## Compatibility, rollback and affected steps

EC-12's read/validate/mutate/readback principle and EC-16 remain binding; the
rename-then-body example applies to historical v1, while the selected new mode
commits authoritative name/state/body together. See the linked EC-12 amendment.

- RP-009: bounded native document layout and artifact descriptors; capacity and
  admission backpressure must account for full-record contention and API limits.
- RP-010/011/012: role-level mutation rules, correlated statuses, timing and
  authenticated gateways; no v1/v2 mixed writers in one authority.
- RP-015/016/017/018/019: actual conditional adapter, readback recovery, election,
  effect barrier, role separation, alternate-storage qualification and setup.
- RP-026/028/030/036/037/038/043/044: mediated network/launch/execution effects,
  enrollment/reconfiguration, process containment and no bypass during takeover.
- RP-047/048/049/050: one-result reconciliation, immutable identity, artifact
  integrity, finite retained evidence and guarded recycling.
- RP-051/052/057/058/060/061/062/063/064: compatible repository instructions,
  packages/migration, negative tests and real multi-host/provider acceptance.

The listed existing step definitions keep their original acceptance meanings;
this amendment is an added binding implementation constraint, not completion.
Rollback cannot lower epochs, restore an old control snapshot as live authority,
re-enable old unfenced actors, or erase uncertain/unconsumed work. Before live
migration, prepare an explicit version/capacity/in-flight/credential isolation
procedure and obtain the specific owner authorization. Public design rollback
requires a later recorded amendment; preserve this decision and experiment history.
