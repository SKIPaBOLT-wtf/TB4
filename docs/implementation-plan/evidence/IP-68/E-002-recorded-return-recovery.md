# IP-68 Evidence E-002 - Recorded-return recovery build

Date: 2026-09-30. This is progress evidence, not completion of the private pilot.
Authoritative step status remains in `../../manifest.yaml`.

## Owner-host observation and preserved evidence

After the registered-device TreeAuditor fix in PR #5, the owner supplied WATCHDOG
telemetry showing RUNNING / ROLE_LOOP, a successful Drive metadata read and no
reported error. Before that check, the owner supplied FETCHER cooperative-exit
telemetry. These are owner-provided runtime observations, not CI simulation.

Independent authenticated Drive reads still found the earlier cancellation test
in FETCH_BALL_RETURNING and its STOP_BALL_ACKNOWLEDGED. Separate copies were
created under the target's canonical BONEYARD and read back with matching content
and correct parents. The reviewed FETCH_BALL result hash and inline payload hash
were recomputed and matched. No live control body, filename, identity, root or
job generation was changed during this preparation.

The retained output includes the post-wait marker. This is NOT proof that the
intended wait was interrupted. Issue #7 tracks cancellation timing and natural-
exit classification; it remains an open acceptance gate. The exact cause of the
original provider conflict is also not proved by this recovery change.

## Implementation and source provenance

PR #6 adds the explicit FETCHER-only **Recover recorded return** action. See
`../../../RETURN_RECOVERY.md` for the operator prerequisites and safety boundary.
The action validates an explicitly reviewed result and its separate archive,
checks stale FETCHER heartbeat and ownership, and uses the existing fenced
FETCHER RETURNING-to-recorded-terminal transition. It never executes, reclassifies,
clears or recycles the prior job. Ordinary role startup is unchanged.

- PR head: `3d801cf5e97b7400203e66a78de8de57e2a048cf`.
- Tested synthetic merge: `e41811296a117ad66e680ebc434f858a4c0042be`.
- Actual merged commit: `5d78f7b43d374ee4d3dbe5b3da1b238358517b02`.
- Both merge commits have the identical source tree
  `cec3750473f9d3be769f67738cff8b219d51495d`, verified through Git data reads.

Existing-file diffs for app.py, entry.py and worker.py were reviewed. The
publication helper, regression tests and documentation are isolated additions.
No protocol vocabulary or ordinary execution-loop rewrite is included.

## Automated verification

- CI run `36652435686`, job `109689410131`: success. Logs report
  **645 passed, 2 skipped** and a clean public repository security scan.
- Desktop run `36652435760`: Linux job `109689410355` and Windows job
  `109689410520` both completed successfully. Both ran the GUI suite, built both
  applications and passed packaged installer acceptance. The complete regression
  suite also passed in the Linux job; that step is intentionally skipped on Windows.
- The downloaded Windows archive's acceptance.json reports PASS for bundle self-
  test, GUI smoke, and install/uninstall/profile isolation for both roles. Its
  scope is explicitly `credential-free-platform-CI`, not live Google Drive access.

## Verified Windows distribution

Windows artifact ID: `11070987233`, from Desktop run `36652435760`.
Archive: 119047368 bytes; recomputed SHA-256 matches GitHub's artifact digest:

`f3478e8b0ed42a7aba7193df2e25b3de01500f47e7c3d7ac3606bf23cff1ba32`

Both installer hashes were recomputed and matched the archive's SHA256SUMS.txt:

| Installer | Bytes | SHA-256 |
| --- | ---: | --- |
| TB4-fetcher-0.0.1-windows-x64-setup.exe | 60059865 | 30d7ca2a96f3b89d83090478d06a1f59a256d467a3bf43aa489d848006fef6a1 |
| TB4-watchdog-0.0.1-windows-x64-setup.exe | 60061972 | cc62bdc1ddcc6fdac0c0f43892dc6d8c9a40cb992980037132301a003d445444 |

Only the FETCHER installer is handed to the owner for this step. The already-
working WATCHDOG need not be reinstalled merely to add a FETCHER repair action.
Version 0.0.1 alone does not distinguish these pilot builds; use the hashes and
source/build provenance above.

## Remaining gate and rollback (pre-installation checkpoint)

At this evidence checkpoint the new FETCHER build has NOT yet been confirmed
installed on the owner workstation, and real recorded-return recovery has NOT
been performed. Canonical recycling, effective cancellation and remaining pilot
scenarios are still pending. Neither this build nor a future publication-only
repair constitutes full IP-68 acceptance.

Before upgrading, exit the stopped FETCHER tray application and preserve the
previous installer and private profile. Reinstall the previous installer to roll
back binaries. Do not delete the root, copy another role's credentials, rewind
Drive lifecycle state or replay an old generation as rollback.

Private object IDs, host paths, identity details, actual request bodies and OAuth
material are intentionally omitted from this public progress record.

## Live publication and supervised recycling update - 2026-09-30

This later checkpoint supersedes only the pending installation/publication/
recycling observations above; it does not erase their chronology or complete IP-68.

The owner reported installing the handed-off FETCHER update and seeing the new
Recover recorded return button. After submitting the reviewed recovery ticket,
the owner supplied EXITED / ACTION_FINISHED telemetry with FETCH_BALL_CANCELLED,
a successful metadata read and no reported error. Independent authenticated
Drive readback confirmed the same canonical object in FETCH_BALL_CANCELLED with
the original report unchanged. No new execution-start or finish evidence was
created. The delivered installer was verified as recorded above; its installed
host binary was not independently rehashed at this checkpoint.

Before recycling, COACH reread the current PARK_MAP, live terminal report,
STOP_BALL acknowledgement, and both separate BONEYARD copies. The recorded
FETCH_BALL and STOP_BALL result hashes and the inline payload hash were recomputed
and matched. The original report still contains the post-wait marker; this was
consumed as unresolved cancellation-test evidence, not a passed interruption.
The observed global fault object was CLEAN. The target heartbeat was unchanged
from the stopped FETCHER instance; no role loop was started during this action.

With the owner-confirmed FETCHER stopped, supervised exact-ID connector calls
performed these separate canonical COACH paths:

- STOP_BALL_ACKNOWLEDGED -> STOP_BALL_RECYCLING -> STOP_BALL_READY.
- FETCH_BALL_CANCELLED -> FETCH_BALL_RECYCLING -> FETCH_BALL_READY.

Each RECYCLING filename and retained operation/generation was read back before
clearing its body. Prepared idle bodies were checked against the connector-read
schema constraints. Each replacement was read back before READY publication and
matched the prepared bytes. Final independent reads confirmed both READY names
and their idle bodies. Stable control object IDs, parents and the existing
channel generation were preserved; no new generation or executable payload was
published. Archived original reports were not modified.

FETCH_BALL uses the idle-body shape exercised by simulation.recycle_job.
STOP_BALL retains only the previous target/job linkage strings required by its
current schema; operation_id, request/acknowledgement data, hashes and timestamps
are cleared. Its READY filename and null operation_id do not represent a live
cancellation request. No placeholder target or invented job identity was used.

These were supervised COACH connector operations, not an automatic recycler or
a test of concurrent writers. The connector mutation arguments used do not
expose an atomic version precondition. No retry was needed, and this checkpoint
does not establish provider-level compare-and-swap safety.

The next local gate is a fresh FETCHER role-loop start observing the idle
channels. That restart is not yet verified here. Effective cancellation and
natural-exit classification in issue #7, plus the remaining pilot scenarios,
still require separate evidence. Do not rewind the published lifecycle or
restore an old executable request as rollback.
