# Native authority transactions (RP-015, unreleased)

The selected R2 transport uses one commissioned native Docs document and fixed
tab. `NativeDocsAuthority` provides actual Docs request construction around an
injected authorized service. `RecordMutation` and `reconcile` implement bounded
same-operation reconciliation. Neither is connected to the installed v1 runtime.
No credentials, creation, discovery, deletion, raw-file rename or payload execution
is exposed by this interface. A missing authority never creates a replacement.

## Provider boundary

Read the exact document with all tab contents and inline suggestions visible;
require the configured single tab, canonical bounded JSON, matching domain and a
nonempty opaque caller-specific revision. Extra tabs, child tabs, rich structural
content, suggestions, invalid indexes and malformed records stop mutation. Plain
style metadata is nonauthoritative. The initial section break and final newline
are preserved. Snapshot bytes are immutable and edits get fresh decoded values.

One `batchUpdate` deletes the old JSON text and inserts the new text, with both
ranges explicitly addressing the configured tab and `requiredRevisionId` from
that observation. Indexes count UTF-16 code units. The terminal newline is excluded
from deletion and insertion. No `targetRevisionId`, unconditional fallback or
SDK request retry is used. A snapshot cannot be passed to a different adapter
instance/principal. Revisions are never numeric epochs or compared across users.

Google documents atomic batch application and rejection of an outdated required
revision with HTTP400. A generic400 is not necessarily a race: fresh readback with
the same revision returns REJECTED, while a changed revision permits bounded
revalidation. [Provider batch contract](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate).

The API counts UTF-16 indexes and cannot delete the terminal newline. It strips
BMP private-use characters during insertion; this adapter escapes that range in
JSON and checks actual encoded slot/document budgets, preserving decoded values
and hashes. Other Unicode, including supplementary characters, remains intact.
[Request contract](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request).
Reads use the explicit tab representation described in [the tabs guide](https://developers.google.com/workspace/docs/api/how-tos/tabs).

## Application boundary

A record mutation freezes its domain/header, caller-pinned owner and epoch,
protected records, and exact before/after records. Leadership heartbeat changes
and unrelated slots may change without invalidating that business operation.
Current ACTIVE owner/epoch and absence of a pending forced request are checked on
every fresh observation. Old actors do not adopt a newly observed owner identity.
Generic record updates cannot change leadership or forced requests; election is
the separate RP-016 transition path using the same strict document CAS.

After a rejected CAS, read again, preserve unrelated updates, revalidate complete
guards and retry only a still-applicable transition. Different operation,
generation, payload/result, owner or forced request cannot be overwritten to make
publication succeed. No all-target acknowledgement barrier is introduced.

After an accepted or ambiguous request, only read the same operation. Full desired
record equality, protected binding and owner guards establish CONFIRMED; exact
receipt-version equality is unnecessary. Stale/absent readback cannot prove a
lost request never applied. UNKNOWN stays inspect-only. SUPERSEDED and CONFLICT
are distinct from successful confirmation, including after a possibly applied
write. Results never authorize process execution or replay.

`mode=START` requires a durable pre-send intent. After any possibly sent request
or restart, use `mode=INSPECT` with the same saved mutation. The runtime must
persist those bytes and the uncertainty before dependent actions (RP-047).
The helper does not claim crash durability. Default budget is6 reads/3 writes;
hard bounds are12/4. Call count is bounded, not HTTP wall time. Runtime wiring must
supply response-size limits before parsing, bounded HTTP timeouts, rate/backoff
and protected credential/role enrollment. The injected service's automatic
authentication behavior must also be qualified; `num_retries=0` disables the
request SDK's retries, not every possible lower transport action.

`terminal_publication` ports RP-013's invariant: an already present, validated
RETURNING result and matching work/status become UNREAD/AWAITING_CONSUMPTION
together. It checks domain, target, operation, generation, protocol, payload hash,
result hash/semantics and expected stage. It never runs work or obtains a result.
Its caller must have role authorization and durable result proof. The pinned
owner guard is a cooperative current-epoch guard, not a FETCHER credential;
RP-017/043/047/048 must bind the actual writer and durable outbox. In-flight work
survives owner takeover and is not replayed by this helper.

## Conformance and remaining gates

The shared reconciler suite runs on the actual Docs request adapter with a
synthetic wire service and an independent atomic mutation model. It covers benign
metadata/heartbeat changes, stale ownership/request flags, complete binding,
delayed readback, ambiguous apply/lost reply, unchanged-revision rejection,
idempotent completion, contention bounds and atomic whole-record publication.
Wire tests inspect document/tab/revision/ranges, Unicode, errors and malformed
content. The old raw-file RP-013 counterexample remains a normal negative test;
its required positive invariant is now tested on this selected R2 implementation.

The historical v1 runtime is deliberately not made a second authority. DEF-001
remains OPEN for durable outbox, actual runtime role integration, ordinary
publication and end-to-end acceptance. RP-008's isolated real CAS evidence proves
the primitive, not this adapter's full real deployment behavior. Provider
throughput, ACLs, deadlines, multi-host/runtime recovery and real-provider pilot
are separate gates. The application is cooperative: a malicious unrestricted
Docs editor can bypass these checks. Shared-state CAS cannot revoke already
dispatched OS/network effects.

Rollback of this unreleased implementation removes its additions. It never
restores an older live authority snapshot, re-enables mixed v1/v2 writers,
rewinds generations or clears uncertain work. Deployment/migration needs separate
authorization and its own acceptance evidence.
