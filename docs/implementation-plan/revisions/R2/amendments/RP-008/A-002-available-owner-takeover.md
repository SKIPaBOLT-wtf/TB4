# RP-008 amendment A-002: stale-record takeover without acknowledgements

Date: 2026-09-30. Authority: explicit owner correction in RP-008-A002-0013;
implementation intent RP-008-A003-0001. This supersedes A-001's mandatory
all-sink drain/acknowledgement prerequisite for WATCHDOG role activation.
Native Docs sole-authority selection remains approved. No live migration grant.

## Owner decision and corrected invariant

The owner rejected waiting for every execution location: a computer can power off
unexpectedly, and WATCHDOG duties must be taken over without contacting it.
A stale ownership record is sufficient to attempt takeover. The first successful
conditional claimant becomes ACTIVE immediately. The GUI must show the current
WATCHDOG computer name and provide a forced-takeover request. Other WATCHDOGs
check the request/current owner before changing shared records.

This is a deliberate availability choice. A-001's global effect-barrier model
and A002 acceptance receipts remain historical evidence for the rejected policy.
They do not establish the current policy's acceptance. The manifest selects A003
and its new evidence. No failed result, old amendment or historical proof is erased.

Current invariant: one authoritative owner/epoch controls shared WATCHDOG writes.
Old owners cannot commit a shared update after a newer ownership/request revision.
Already admitted external effects are a different scope: role takeover does not
wait for their completion or for a powered-off/unreachable sink. Preserve exact
operation state/results and UNKNOWN effects, without blind replay or fabricated
cancellation. Those operation-specific uncertainties do not block unrelated
WATCHDOG coordination, scanning, summaries or admission to other capable targets.

## Record and arbitration

The one fixed native document holds domain identity, owner installation identity,
private display computer name, increasing leadership epoch, heartbeat timestamp
and sequence, transition ID, and one bounded forced-takeover request slot. Real
computer names remain private deployment data; public tests use synthetic names.
Display names are not unique credentials: duplicate names must not let a different
installation impersonate the owner. Each enrolled instance retains its own identity.

WATCHDOG reads the authoritative record. If its heartbeat is fresh, another
instance remains PAUSED/OLDER_DOG_DETECTED unless an explicit forced request is
issued. If the timestamp is already stale under the commissioned freshness
policy, a newly started instance may immediately attempt takeover on that first
read; it does not need another waiting window or any response from the old host.

Takeover is one strict requiredRevisionId CAS committing the new identity/name,
epoch+1, heartbeat and ACTIVE status. No ACTIVATING/all-sink state intervenes.
Two readers can see the same stale record, so “first reader” is implemented as
first successful conditional claim, not two unconditional writes. The loser
rereads and shows the new owner. A competing incumbent renewal changes revision
and defeats a stale snapshot. Readback confirms the winner before dependent work.

Freshness uses the specified timestamp/timeout semantics from RP-011. Wall-clock
time is not an election tie-breaker. If timestamps cannot be trusted (clock
uncertainty/backward clock), an unchanged heartbeat identity/sequence observed
for a bounded reliable local monotonic window supplies staleness without old-host
ACK. Unrelated record writes do not count as an incumbent heartbeat. This fallback
must not become an indefinite wait. Exact timeouts/clock bounds are set and tested
in RP-011/016; model values are synthetic and not new product defaults.

Shared-authority unreachability prevents authoritative writes, so it cannot be
replaced by an offline ownership guess or second domain. This differs from an
unreachable former WATCHDOG or execution sink, neither of which blocks takeover
when the shared ownership record is reachable and stale.

## Forced-takeover GUI contract

The button is a deliberate local user action on an enrolled WATCHDOG. It publishes
a bounded request containing request ID, requester installation/computer name,
expected current epoch and expiry. The current owner's name stays visible until
the claim commits; the GUI separately shows who requested takeover. No real names
are exported to public diagnostics.

After the flag is read back, its requester conditionally commits ownership and a
new epoch. It does not wait for the current owner's acknowledgement, shutdown or
effect completion, even when the old heartbeat is fresh. This makes the button
an actual forced takeover. Other WATCHDOGs inspect the flag before every shared
mutation, including heartbeat renewal, and cease old-owner writes/new dispatch.
The strict revision check also rejects a write prepared before the flag appeared.

The request is correlated to one owner epoch and one requester; another request
cannot silently overwrite a pending one. A request from a crashed requester
expires by a verified conditional clear. An ordinary stale-owner claim can still
win atomically; that clears the old flag and the obsolete forced claim fails.
A stale request must never transfer a later epoch. The GUI reports requested,
confirmed owner, contention/lost ownership, expired or outcome unknown distinctly.
Lost responses trigger inspection of the same transition ID, never another click
or an assumed success. Owner-directed buttons do not require an extra generic
confirmation or real-time approval round trip to the LLM.

## Writes and already dispatched actions

Every shared control write reads current owner/epoch/request, validates the actor,
and uses the exact document revision in its mutation. An old actor rereading a
new epoch does not acquire that identity. Code must not simply adopt whatever
epoch it sees. This prevents stale authoritative records from being resurrected.

Before new external dispatch, WATCHDOG/helpers also refresh ownership/request and
stop on loss. This is cooperative protection, not an atomic transaction with a
router, OS process or SSH endpoint. An old process can pause after its check and
complete an already dispatched action after takeover. The owner-selected policy
accepts that role availability is not blocked by this interval. Do not claim
zero-overlap external effects or that Docs can revoke OS privileges instantly.

Preserve operation identity, deduplication and command-specific busy/UNKNOWN
handling. Uncertain old work is not silently re-executed, recycled, cancelled or
marked successful. Any stricter fence supported by a particular target may be
used locally, but it is never a mandatory global role-activation barrier. Explicit
network/action authorization remains required; ownership alone grants no new
permission to change devices, credentials or network configuration.

## Changed acceptance interpretation and affected steps

Original RP-016.C2/C4 required rejecting every stale action and proving no two
actors perform any protected work. For this owner-approved policy, prove exclusive
authoritative shared-state mutation and cooperative checks before new dispatch;
explicitly test and preserve the external check/dispatch suspension limitation.
Do not reintroduce all-sink ACK, an old-host response, or manual LLM intervention
as a prerequisite to stale-record or forced role takeover. EC-16 amendment A-001
and current R07/RP-016 text make this change explicit rather than silent.

RP-009/010 define the bounded ownership/request slot and correlated statuses;
RP-011 defines freshness/request expiry; RP-012 documents the actual guarantee;
RP-015/016/017 implement conditional writes, ownership and role isolation;
RP-018/019/030 preserve one authority during setup/alternate storage;
RP-026/036/037/038/043/044/047/048 retain per-action authorization and uncertainty;
RP-053 adds owner/requester names and forced takeover to the GUI; RP-058/060/063/064
must test powered-off owner, unavailable sinks, simultaneous claimants, resumed
old writer and forced takeover without peer acknowledgements. No UI completion is
claimed by this design step; implement the UI when its actual dependencies pass.

## Evidence, compatibility and rollback

`tools/experiments/available_takeover.py` and corresponding feasibility tests are
the A003 executable design. Historical `docs_authority.py` remains the rejected
global-barrier comparison, not the selected mechanism. A001's isolated real Docs
CAS result still supports the conditional-write primitive; it is not a deployed
multi-host runtime test. Actual adapters, authorization, GUI and provider/native
pilots remain later acceptance gates.

The native-document transaction, fixed identities/capacity and nonauthoritative
raw projections in A-001 remain applicable except where this amendment explicitly
replaces activation/effect guarantees. Never mix v1 raw mutable control with this
authority, rewind epochs or erase uncertain operations during rollback. A future
live migration still requires its separate explicit authorization and validation.
