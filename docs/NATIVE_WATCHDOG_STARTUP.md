# Native WATCHDOG startup and standby (RP-017, unreleased)

The native role factory accepts an explicit `NativeWatchdogContext`. It routes
to `NativeWatchdogRuntime` before the historical runtime's eager tree repair,
registration or scheduler composition. Desktop `run_native_watchdog` uses that
same factory and publishes its local role state. A valid incumbent produces
`PAUSED / OLDER_DOG_DETECTED`. The existing status pane renders that reason.
No host name, credential locator or raw provider exception enters telemetry.

This is a new R2 composition boundary, not a v1 migration. Existing installed
profiles still select their historical v1 implementation. A CAS lease must not
be put alongside independently mutable v1 command files. The native entry cannot
fall through to legacy discovery/repair/registration; later commissioning must
explicitly construct its one-document authority, protected local store,
capability resolver, qualified clock and work adapters. There is no implicit
provider fallback, second authority or supplied in-memory production store.

## Role lifecycle

Construction checks private installation/store binding and performs no shared
read, mutation, scan or work-adapter construction. Standby observes only the
configured native authority at the RP-011 standby cadence (default10s), plus
local status/checkpoint/capability access. It never calls the work scheduler.
It does not copy another installation's identity, grant, profile or secrets.

A stored grant is validated against the current owner/epoch/acquisition and
request slot. An owner display name, or even this installation's UUID in a
fresh shared record, cannot manufacture a missing local grant. A valid saved
grant can resume on the same installation after fresh validation/renewal.
Authority or capability loss pauses admission; rejoin inspects current state.

A stale incumbent is claimed with RP-016 direct ACTIVE CAS/readback. A matching
valid force request can claim immediately while the incumbent is fresh. Neither
path waits for an old host, sink acknowledgement or unknown older action. Clock
uncertainty uses qualified monotonic observations; unreliable/backward local
monotonic samples pause/reset the observation window. The active role renews at
the configured lease cadence and checks control on the independent control
cadence. Long provider/action calls still need qualified timeouts and scheduling
in their later adapters; this loop is not a real-time deadline guarantee.

## Durable intent and work boundary

The protected checkpoint port is installation- and authority-bound. It must
provide exclusive durable atomic compare/replace plus readback before an
election, shared write or external call. A possibly sent election is persisted
and resumed only through INSPECT. An already superseded election does not block
future eligibility; it clears only the local grant/pending pointer. No shared
owner/epoch is reset. The native entry requires its caller to hold the qualified
local instance lock; store/ACL/clock assembly and durability remain commissioning
gates, with synthetic ports used for this step's boundary tests.

Every new work request has a closed Action and caller-assigned unique operation
ID. Shared actions (repair, registration, identity, routing, retention) provide
a pure preparation function returning an exact RP-015 RecordMutation. They
cannot return a typed election subclass or use this API for raw file writes.
The actual write revalidates owner/epoch and strict document revision. External
scan/WOL/SSH/launch ports represent one bounded fixed action. Their own approved
local capability must match the installation, and ownership/request is checked
again after durable intent immediately before dispatch. Credentials stay inside
those commissioned adapters; a callable is trusted program composition, not an
ACL or authorization token accepted from the LLM/shared document.

One current receipt per action bounds local state. UNKNOWN is recorded before
dispatch; exceptions/ambiguous outcomes retain it across restart. The same or a
new operation of that action cannot replay while its outcome is unknown. Other
independent actions and leadership can continue. A shared pending mutation is
inspected without writing, and cannot be overwritten by another work kind.
External-result reconciliation and the full durable operation/receipt engine
remain RP-031 onward; this bounded role checkpoint is not an unlimited job
deduplication ledger. Work adapters must preserve their own operation binding,
semantic acceptance and history before exposing COMPLETE or a new operation.

No callback is constructed by the local scheduler before active-owner admission.
That scheduler and shared preparation functions must be pure/local; external
effects belong only inside the named single-action port. This cannot sandbox
malicious Python adapters or a writer bypassing the native authority. A process
may still suspend after external admission and resume after another owner wins;
RP-008 A-002's overlap limit remains. Shared writes are strictly fenced, while
already-dispatched effects remain individually uncertain and are not replayed.

## Acceptance boundaries and rollback

Tests compose actual native request construction, role factory, desktop worker
and telemetry with independent synthetic installations, clocks, local stores
and work ports. They qualify incumbent-first orchestration/admission, not the
future network, commissioning, OS secret-store or full command-engine adapters.
Original v1 tests remain compatibility coverage and do not prove v2 leadership.
Native GUI/package checks qualify packaging/import/status compatibility only.
No installed process, provider document or live domain is changed here.

Rollback removes the unreleased native entry or stops its local admission loop;
never clear another valid owner, lower an epoch, erase an UNKNOWN receipt, copy
another installation's profile or silently reactivate v1 writers in a v2 domain.
