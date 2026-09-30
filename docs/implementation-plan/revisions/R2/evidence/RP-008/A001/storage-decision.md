# RP-008 storage exclusion decision — review candidate

Date: 2026-09-30. Authority: R07/R08/R10/R18, RP-008, EC-16 and the realignment
single-domain requirement. This record proposes a decision boundary; step status
and accepted checks remain in the manifest. Prototype validation is recorded
separately; passing counterexample tests do not make an unsafe mechanism safe.

## Problem and inspected implementation

Current `GoogleDriveBackend` advertises `atomic_version_precondition=False`.
`rename`/`replace_text` first call `_check_expected_version` and then issue an
unconditional `files.update`. The expected version/leadership epoch is not part
of the mutation request. `read_text` obtains metadata and media in separate calls.
Stable object identity and one rename request do not establish a shared ownership
transaction. Source pointers: `src/tb4/drive/backend.py`, `google_backend.py`,
`runtime_support.py` and `desktop/profile.py` at the experiment source commit.

`InMemoryDriveBackend` simulates version-checked transitions in one object store;
it is not a cross-process, durable, distributed provider guarantee. Existing
desktop profile locks prevent duplicate use of a local profile; they do not
coordinate independent machines or a Drive sync replica. The production default
constructs GoogleDriveBackend. No qualified shared-folder adapter exists yet;
RP-018 explicitly requires qualification of a particular mode and same-exchange
LLM access, not a generic claim about every filesystem.

## Actual interfaces and provider guarantees

| Surface | Verified capability | Missing safety boundary |
| --- | --- | --- |
| Current raw Drive adapter | Exact IDs, reads, replace, rename, move; precheck version | No conditional mutation sent; metadata/body read can span versions |
| Available Drive `update_file` connector | Same-ID raw bytes or metadata/parent update | Exposed schema has no expected version, ETag, epoch or conditional header |
| Available Docs `batch_update_document` connector | `write_control.requiredRevisionId` and `targetRevisionId` explicitly exposed | Applies to native document content, not arbitrary Drive metadata/files or local effects |
| Available Docs `get_document` connector | Native document/revision access API is exposed | Actual access to a particular document and each principal must still be verified |
| In-memory/local-profile primitives | Synthetic serialization / local exclusion | No shared durable authority or remote revocation of old actors |
| Proposed shared folder | RP-018 planned qualification | Sync presence alone does not prove locking, remote visibility, durability or LLM connector access |

Primary references inspected on the date above:

- [Drive files.update](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/update)
  lists update parameters without an update-if-version parameter. The inspected
  adapter and connector send none. This is **not** a proof that every conceivable
  Drive HTTP mechanism is impossible; a new header-based adapter needs specific
  documented support and isolated qualification before selection.
- [Drive File resource](https://developers.google.com/workspace/drive/api/reference/rest/v3/files)
  makes `version` output-only and increasing across server changes. File
  capabilities concern the caller's access, not exclusive leadership.
- [Drive batch semantics](https://developers.google.com/workspace/drive/api/guides/performance)
  split batches into separate calls, may process them in any order and do not
  batch media operations. A grouped lease-and-file write is not a transaction.
- [Docs batchUpdate / WriteControl](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate)
  documents atomic updates within one request and rejects a stale
  `requiredRevisionId`. `targetRevisionId` merges collaborator changes instead;
  it is unsuitable as a strict ownership precondition. This is a real candidate
  primitive, not an unavailable connector capability.
- [Docs Document revision](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents)
  is an opaque, user-specific value with a limited validity guarantee. Each
  principal must read its own current revision; it is not a shared numeric epoch.
- [Drive permissions](https://developers.google.com/workspace/drive/api/guides/manage-sharing)
  distinguish roles and file capabilities. Sharing credentials or write access
  does not establish a leader epoch; no ACL or credential was changed here.

General HTTP ETag examples, Calendar APIs, historical v2 snippets and a successful
unconditional write are not evidence that this selected v3 adapter conditionally
fences writes. Provider error/freshness behavior must be qualified, not guessed.

## Isolated prototype and falsifiable predictions

`tests/feasibility/test_storage_fencing.py` exercises the actual Google adapter
with a deterministic synthetic provider schedule: A passes its precheck and
suspends; B claims and verifies; A resumes, overwrites and verifies. Both calls
can report success. A separate schedule changes the body between metadata/media
reads. These tests intentionally preserve counterexamples, not repair runtime.

`tools/experiments/storage_fencing.py` models an explicitly ideal atomic authority.
Candidate tests cover all six orders of three simultaneous contenders, valid
incumbent preference, delayed observations, partitions, suspension/return, expiry,
clock uncertainty, missing commissioning authority and wrong-domain snapshots.
Atomic ownership **and effect** validation at one boundary rejects stale writes.
A CAS lease followed by a separate unfenced write still admits a stale effect
after takeover. Two independent sync replicas can each grant ownership.

Model assumptions are stronger than the current implementation: linearizable
compare-and-mutate, authoritative monotonic time and indivisible validation/effect.
The model proves behavior under those hypotheses, not that Drive, SMB, NFS,
Windows locks, a router or arbitrary SSH commands provide them.

## Commissioning and ownership constraints

Before a shared root exists, a local setup session may prepare an unpublished
candidate only under owner-selected commissioning authority. It must not activate
network maintenance, claim an unverified same-name folder or create a second
domain to bypass a collision. Bind an explicit domain UUID, selected storage
authority identity and enrollment to each installation. Resolve any existing
domain/incumbent and interrupted setup before publishing one fixed control tree.

A healthy valid incumbent wins; standby is PAUSED with reason
OLDER_DOG_DETECTED. Calendar age, filename order, last heartbeat and cached reads
are not leadership. Concurrent candidates must arbitrate in the shared authority;
nonwinners remain passive. Epochs increase at takeover and never reset on reboot,
re-enrollment or rollback. Each installation has separate identity/credentials.

Takeover cannot become ACTIVE until old protected writes/effects are fenced at
their actual sink. A lost lease, uncertain clock or disconnected authority stops
new protected work. Already-dispatched or ambiguous effects require inspection
of the same operation, not replay. A local check immediately before a remote action
still has a suspension window. An unreachable unfenced sink cannot be declared
safe merely to maintain automatic availability.

## Candidate comparison and owner decision proposal

1. **Current raw Drive checks/readback:** reject for automatic takeover. More
   polling, timestamp comparisons, random delay, election tie-breakers or another
   post-write read cannot remove the precheck/write race.
2. **Native Docs CAS lease plus existing raw mutable files:** reject as a complete
   solution. It improves lease arbitration but leaves separate writes/actions
   outside its atomic/fencing boundary.
3. **One fixed native Docs authoritative ledger in the same TB4 domain:** plausible
   storage candidate. All leadership and authoritative control mutations would
   use that document's strict revision precondition; raw file views would become
   nonauthoritative projections. This changes the selected raw-object transport
   and schema/layout contract, so requires an explicit owner-approved amendment.
   It also needs a separately proved sink-fencing design for each protected local
   or network effect. It is not accepted or deployed by this investigation.
4. **Qualified shared-folder authority:** potentially testable under a specifically
   selected filesystem/protocol and same-exchange connector. Generic synchronized
   copies do not qualify. Switching away from the selected Drive mode or creating
   a second coordination service is not an automatic fallback.
5. **Disable automatic takeover:** a possible owner-directed scope change only;
   it does not satisfy R07, RP-008 or RP-016 as currently written.

Proposed narrow owner action if tests confirm these boundaries: authorize a design
amendment for candidate 3, retaining one TB4 domain and mandatory effect-sink
fencing. That permits design/prototype qualification, not live migration and not
claiming automatic fallback solved. Alternatively the owner may explicitly revise
the fallback requirement or nominate a different single authoritative storage
mode. Do not silently make that product/transport choice during implementation.

Until resolved, preserve C1-C3 evidence, leave C4 and RP-008 unaccepted, and do not
start dependent RP-009/010/015/016/018. Check other ready steps against their actual
dependencies before any recorded schedule exception; do not bypass this gate.
No real root, lease, service, network, credential or installed profile is changed.
