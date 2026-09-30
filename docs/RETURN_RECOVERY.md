# Explicit recorded-return recovery

This is a repair path for IP-68, not automatic execution recovery or a new protocol state.

## Why an explicit action

A previous FETCHER can write a complete terminal report while its final filename
publication fails. On restart, the existing service deliberately identifies
`INCOMPLETE_RETURN`; it must not rerun the old payload. Ordinary Start still does
not complete or clear that report. A healthy WATCHDOG startup does not prove this
work channel has recovered.

The FETCHER desktop app now exposes **Recover recorded return**. It runs a
separate, short-lived worker action called `recover-return`, while holding the
FETCHER profile lock. A legacy service is refused. No role loop is started.

## Preconditions and operator review

Stop every FETCHER instance for the selected target and establish that the old
execution is no longer running. A stale heartbeat is only an additional guard;
it does not by itself prove arbitrary orphaned child processes are dead.

Read the exact canonical FETCH_BALL from the current PARK_MAP. Preserve a separate
byte-identical copy under that target's BONEYARD and verify it remotely. Review
the recorded operation, generation, output/effect evidence and result hash before
issuing the ticket. Preserve related STOP_BALL evidence as well when relevant.

The GUI accepts only these ticket fields:

- `operation_id`: the exact reviewed operation identity;
- `generation`: its exact integer generation;
- `result_sha256`: its reviewed complete-result SHA-256;
- `archive_id`: the stable ID of the separate matching BONEYARD copy;
- `reviewed`: explicitly `true`.

These are private deployment values. Do not commit real tickets, object IDs,
request payloads, credentials or tokens to this public repository.

## What the action checks and changes

The action resolves the target from saved configuration and the current PARK_MAP,
not from ticket-supplied control IDs or a mounted folder. It checks the report
schema, operation/generation, complete-result hash, inline payload hash when
applicable, stable metadata observations, correct parent folders, and a separate
matching archive. Fresh, future-dated, invalid or unreadable FETCHER heartbeats
prevent takeover. The guard uses the configured maximum idle/active stale horizon
plus the FETCHER grace period.

Only an already-written `DONE`, `PARTIAL`, `FAILED` or `CANCELLED` result with
execution-start and finish evidence is eligible. The existing StateWalker performs
the legal FETCHER `RETURNING -> recorded terminal` edge with generation fencing.
The result is read back again after publication. The archived and live body bytes
remain unchanged.

The action never executes a payload, creates a new generation, changes result
classification, claims CHEW, clears STOP_BALL, resets the root, or recycles a
channel to READY. Repeating the same reviewed ticket while stopped can observe
an already-published matching terminal result without another mutation. Any
conflict or ambiguous outcome requires inspection of that same operation rather
than a replacement request.

## After publication

COACH must consume/reconcile the retained result and any STOP_BALL acknowledgement
before the separate canonical recycling steps. Recovering the publication does
not make the original job or the entire pilot a success.

In particular, a recorded CANCELLED result whose output contains the test's
post-wait marker is not evidence that cancellation interrupted the intended wait.
Its exact output must remain intact, and cancellation timing/classification must
be investigated and retested separately. Hash integrity establishes that the
reviewed record is unchanged, not that its semantic classification is correct.

## Verification and rollback

Automated tests cover unchanged body bytes, no subprocess execution, exact-ID
operation, ticket mismatch, state mismatch, archive tampering or wrong parent,
fresh heartbeat, repeated publication, stop requests and rename conflicts. GUI
tests cover role isolation, active-worker exclusion, malformed input, cancellation
and explicit confirmation. Packaged acceptance imports the recovery helper.

Real owner-host recovery remains a separate pilot gate. Before binary upgrades,
stop the affected worker and exit its tray app. Preserve the previous installer
and the private profile. Reinstall the previous binary to roll back the app; do
not rewind Drive lifecycle state, remove evidence or replay a job as rollback.
