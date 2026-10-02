# Mandatory TB4 development and debugging instruction

Version: R2, 2026-09-30. Applies to every RP step, subcheck, investigation, repair,
configuration experiment and release action once that scope is authorized.
This instruction is a development contract, not a grant to operate a deployment.

## Contents

1. Authority and minimum cold-start reads
2. Permanent IDs, ownership and records
3. Write-ahead checkpoint rule
4. Action/test/acceptance loop
5. Abrupt interruption and GitHub outage
6. Debugging without losing provenance
7. Privacy and portable setup
8. Completion and handoff gates

## 1. Authority and minimum cold-start reads

Read AGENTS.md, docs/implementation-plan/CURRENT.yaml, the active revision README,
this instruction, its manifest, docs/development/RESUME.yaml, the indicated step,
and only that attempt's latest journal/evidence and relevant defects. Read the
realignment baseline and R2 OWNER_ADDENDUM when not already loaded. Do not load
the entire project or infer progress from conversation history.

The active revision manifest alone is status authority for its RP IDs. Legacy
IP statuses describe historical scope, not completion of R2. CHECKLIST.md and
per-step checkboxes are projections of manifest.completed_checks/status.
RESUME.yaml is the navigation cursor, not an independent proof of completion.
Journal events establish what was intended and observed; evidence establishes
acceptance. Any disagreement must be reconciled before new mutating work.

The original planning checkpoint has been superseded for ordinary implementation
by ../implementation-plan/revisions/R2/IMPLEMENTATION_AUTHORIZATION.md.
CURRENT/manifest/cursor record that later scope. A general development authorization does not authorize
network reconfiguration, credential disclosure, destructive reset or live workload
replay. Obtain the relevant specific authorization at those boundaries.

## 2. Permanent IDs, ownership and records

Use RP-001 through RP-064 as stable steps, with subchecks RP-xxx.C1 etc. Never
renumber accepted IDs. A changed contract gets an amendment and, when needed,
a new check/step; do not silently replace the meaning of a completed checkbox.

For step RP-xxx and attempt A001 (A002 on reopening), use:

- Definition: docs/implementation-plan/revisions/R2/steps/RP-xxx.md.
- Journal: docs/development/journal/RP-xxx/A001/events.jsonl.
- Evidence: docs/implementation-plan/revisions/R2/evidence/RP-xxx/A001/.
- Amendments: docs/implementation-plan/revisions/R2/amendments/RP-xxx/.
- Defect index: docs/implementation-plan/revisions/R2/defects.yaml.
- Work cursor: docs/development/RESUME.yaml.

A public issue/PR is a useful discussion surface, not a substitute for these
records. Link issue, step, check, attempt, source SHA and regression test in both
directions. Do not create an issue for every mechanical action. A task that has
never started has no fabricated attempt or test results.

One active developer owns a step/attempt. Use a dedicated source branch and a
separate sandbox/test environment when required. Do not concurrently edit the
same manifest/cursor or journal. Before each publication read current refs and
use conflict-checked, non-force updates; on conflict reconcile, not overwrite.
Numerical order is the default. Do not start a dependent step before all listed
dependencies are VERIFIED for the required scope. Skipping a blocked earlier
step requires a recorded scheduling decision proving independence; it is not
permission to bypass a required capability. Defect repairs may return to earlier
steps, with dependent acceptance explicitly held for revalidation.

## 3. Write-ahead checkpoint rule

**NO UNRECORDED ACTION. NO NEXT DEPENDENT ACTION BEFORE REMOTE OUTCOME CHECKPOINT.**

Before a source-edit unit, external mutation, diagnostic experiment, test/build,
merge, deployment or rollback, publish an INTENT to GitHub and verify its readback.
It must identify the exact step/check/attempt and action ID, base source SHA,
safe scope, expected result, verification method, rollback boundary and next action.
Only then carry out that bounded unit. A vague "working on RP-015" is insufficient.

After the action, append an OUTCOME referencing the INTENT and record observed
facts, success/failure/unknown state, exact safe test command/procedure, exit code
when observed, affected public source/build SHA, evidence locations and next action.
Persist a source/WIP checkpoint to its work branch where applicable. Do not call
uncommitted changes a recoverable remote artifact. Never commit raw private data
merely to preserve a WIP. GitHub must contain enough sanitized intent to recreate
an interrupted local edit even if its unpushed bytes are lost.

Publish journal append, manifest changes, checkbox projections and RESUME.yaml
in one repository commit when they describe the same progress transition. The
source branch may have a separate commit; the progress record must reference that
exact commit. Verify the resulting ref/file contents before saying it was saved.
A local file, successful upload request or PR opened without readback is not the
required durable checkpoint. Do not force-push, truncate journals or amend away
failed attempts. Corrections append an event referring to the superseded claim.

If diagnostic prose was mistakenly placed in an INTENT's `observed` field,
preserve that event verbatim. A later `CORRECTION` may use the closed
`intent_note_correction` record to relocate exactly that text into its own
`observed` field. It must reference the earlier PENDING INTENT and match its
source, action, check, item and attempt. Only a null replacement is allowed,
once per target. This changes metadata placement, never authorization, action
scope, execution history, an actual outcome or the pending-action state.
New INTENT records must still have `observed: null`; use OBSERVATION for facts.

If an immutable STARTED record incorrectly used `RUNNING` and omitted `run_id`,
append a CORRECTION with the closed `started_metadata_correction` record. Only
`RUNNING` to `PENDING` and an absent run ID to a reference already present verbatim
in its original observation are allowed. Copy that observation exactly and match
item/check/attempt/action/source to the original pending INTENT. No terminal
outcome, authority, launch fact or result changes; no mixed or repeated correction.
The ledger validates a normalized read view while retaining the original bytes.
New STARTED entries must carry a real run ID and valid pending/started outcome.

If an action group was published with lowercase ASCII action IDs, an explicit
`action_case_correction` CORRECTION may project only those prior IDs to their
exact uppercase form. Reference the original INTENT and preserve its item,
attempt, check, source, scope, procedure, expected result and rollback. The old
group and the projected name must not collide with another action. No rename,
mixed/repeated correction or normalization of future malformed rows is allowed.
Original bytes and actual outcomes remain unchanged; ordinary chronological
validation still applies. New records must use uppercase IDs before publication.

A prior OUTCOME/RECORDED source checkpoint may relocate supplementary source
references into a documentation receipt through a closed `source_evidence_correction`.
It must preserve the exact original evidence list and item/check/attempt/action/
source/observation, target only one uncorrected source checkpoint, and supply
nonempty docs-only replacement references matching its own evidence. It cannot
change PASS/FAIL results, INTENT, STARTED or authorization, or mix corrections.
Original bytes and source-path existence remain checked; acceptance receipts
still require actual PASS evidence. New records should use docs receipts directly.

The early RP-001/RP-002 helpers will automate schema validation/projection/publication.
Until they pass, perform the same transaction manually. Their future existence is
not grounds to omit checkpoints now. A lightweight progress validation gate must
not trigger full installer builds for each documentation-only checkpoint.

For a long test/build, publish STARTED with its recoverable run/job identity before
waiting. Record milestones at meaningful completed boundaries, not repeated
unchanged status polls. On returning to the chat, inspect that same run instead
of starting another. Never promise background work without an actual supported
scheduler/runner. Before a user handoff or planned stop, publish the exact expected
user action and wait condition; do not leave only a conversational promise.

## 4. Action/test/acceptance loop

For each subcheck:

1. Inspect the pinned source, current applicable facts and dependencies. Record
   what is known, historical, inferred and still unverified.
2. Write the intended invariant and a failing/regression test or inspectable
   design-validation procedure. New paths/commands are proposals until created.
3. Publish INTENT, perform the smallest scoped change/experiment, then publish
   OUTCOME. Failed tests are results to preserve, not evidence to erase.
4. Run the targeted tests and required negative cases on declared platforms;
   record the exact command, collected test names, environment class, exit code,
   duration if measured, skipped cases and full public source SHA. Private values
   must be supplied locally and never interpolated into a public command log.
5. Inspect the diff, privacy boundary, compatibility, rollback and affected
   dependencies. A green test that no longer tests the intended invariant fails review.
6. Store reviewed evidence and add the check ID to completed_checks with a mapping
   to its evidence. Regenerate projections and publish the cursor's next exact action.

Every step also requires common gates: all its checks accepted; relevant previous
regressions passing; declared platform/topology coverage or explicit unsatisfied
requirements; source/diff review; public-data review; rollback tested or its
irreversible limits documented; remote progress readback. Only then mark VERIFIED.
Tests skipped for missing hardware/access are not passing acceptance. A design
step can be VERIFIED for its design artifact without claiming the runtime feature
exists. Subsequent implementation/real-pilot gates remain separate.

No test-count-only acceptance. No "GUI RUNNING therefore transport works".
No "body DONE therefore terminal publication succeeded". No "CANCEL_SIGNALLED
therefore execution was interrupted". No "local sync write therefore remote
commit". No successful repair as proof that ordinary operation is fixed.

## 5. Abrupt interruption and GitHub outage

A program or chat can die before writing its last outcome. Documentation cannot
make that impossible. The guarantee is a remotely saved pre-action intent and an
explicit UNKNOWN/unsettled action to inspect, not an invented final result.

On resume: resolve CURRENT, read cursor/journal, find every INTENT without its
matching OUTCOME, inspect the exact work branch/run and actual authorized target
state, then append RECONCILED with evidence or BLOCKED with the missing fact.
Do not repeat a possibly mutating action merely because no outcome was recorded.
Recover a completed build from its run; never assume an old hostname, path, PID,
root ID, deadline or version is still current. An empty orphaned cursor is an
inconsistency, not permission to choose a new task.

If GitHub becomes unavailable before INTENT is durably confirmed, do not start
the action. If it fails afterward, stop new dependent mutations, preserve a
sanitized local pending checkpoint and any protected runtime evidence separately,
and reconcile/publicize the result when connectivity returns. Necessary actions
to prevent imminent harm may proceed only at the smallest safe scope; record
why, then reconcile. Never upload secrets as an outage workaround.

## 6. Debugging without losing provenance

When a mismatch appears, open/reuse a DEF record, mark the affected check/step
not accepted for that scope, and record expected versus observed behavior. Link
the detection step, suspected originating step, affected components and regression.
Set proven_origin to null until a reproduction or bisect establishes it. A repeat
of a symptom does not identify the cause. Keep alternative hypotheses and their
failed tests in the attempt journal, with public-safe evidence.

Use the normal INTENT -> ACTION -> OUTCOME cycle for every diagnostic and patch.
Repair the smallest proven cause. Attach the regression to the responsible step
and update its evidence under a new attempt; do not scatter undocumented hotfixes
into unrelated acceptance steps. No public raw provider errors, topology dumps,
command payloads or tokens to make debugging easier.

A regression invalidates only explicitly affected acceptance scopes, but all
transitive dependencies consuming that invariant must be reviewed. Preserve old
accepted-build evidence; change current manifest status to IN_PROGRESS/BLOCKED
and add revalidation requirements. Re-VERIFY only after linked regression and
required dependent tests pass. Close a GitHub issue only when the acceptance
criteria, not merely the patch or manual recovery, are proven.

## 7. Privacy and portable setup

No real deployment facts in public code, docs, checklists, comments, issues,
PRs, test fixtures, logs, screenshots, artifact names or release metadata. No
secret values in private debug logs either. Use synthetic fixture identities;
hashing an address/account/key is not automatically safe anonymization.

Real topology is protected operational configuration collected locally during
commissioning, not a developer-edited product description. The shared private
BALLPARK is a minimal approved projection, with opaque target aliases and effective
capabilities/timing. Credentials stay in the local approved secret store/key
facility; opaque resolver bindings are installation-scoped and not published in
GitHub. The LLM never needs the underlying passwords, tokens or SSH private keys.

Review exported data before it enters a connector/tool argument or public service.
Use allowlists and canary tests rather than trusting generic regexes or GitHub's
automatic masking. GitHub itself documents that automatic redaction is not
guaranteed: https://docs.github.com/en/actions/reference/security/secure-use .
If protected data is accidentally exposed, stop publication, contain access,
revoke/rotate relevant secrets and document a sanitized incident; deleting a line
from the latest source alone is not remediation.

Code and instructions must derive platform, launch mode, network scopes, storage
identity and credential bindings from first run. Keep OS-specific mechanics in
qualified adapters. Never assume a drive letter, shell path, router vendor,
broadcast reachability, logged-in user, credential location or previous topology.
Reconfiguration/reset use the same verified commissioning model with explicit
migration, in-flight-work protection, identity fencing and rollback boundaries.
A fallback receives its own enrollment/capability bindings, not another host's
identity or secrets. Unsupported capabilities must be visible, not guessed.

The installed SKILL is a pointer only. Real operating/setup procedures stay in
skill/tb4/SKILL.md and its repository-owned compatible references. Refetch at the
next workflow, pin one revision for an in-flight operation, and stop if the
trusted source cannot be read. Do not install a new SKILL or alter operational
behavior as a side effect of editing a development checklist.

## 8. Completion and handoff gates

Before stopping, publish RESUME with step/check, attempt, phase, last verified
source/test/evidence, unsettled actions, exact next action and verification,
blocker/owner decision, rollback and the recorded authorization scope. It must
be enough for a fresh agent to resume without asking for the entire chat.

The R2 manifest records current implementation acceptance under the later authority.
Planning validation is not runtime testing. Public progress entries for this planning
session live under PLAN-R2, never as fabricated RP implementation acceptance.
Use [templates](templates) as the field contract. All future tools must implement
this discipline; tools are aids, not substitutes for verified records.

When a new defect reopens an accepted step, an older resolved defect remains
historically resolved only if its exact accepted attempt survives in acceptance_history
with all reviewed PASS receipts, original matching INTENT/OUTCOME and artifacts.
That historical proof does not accept the new attempt or remove its holds. A
later separate defect in the same reopened attempt uses its own later INTENT;
the first reopening still establishes all historical snapshots and impact.

An affected active dependent that has never been accepted may be explicitly
suspended before reopening its accepted prerequisite, using the closed
`reconciled_unaccepted` repair record described in
`../implementation-plan/revisions/R2/amendments/RP-025/A-001-unaccepted-dependent-reconciliation.md`.
Publish and verify its matching suspension INTENT/RECORDED OUTCOME first, settle
all earlier actions, and preserve the complete public unaccepted snapshot,
attempt/WIP and full revalidation holds. The dependent becomes BLOCKED with no
fabricated accepted history; accepted prerequisites/dependents still reopen in
new attempts with their original acceptance snapshots. Unrecorded or partial
reconciliation, accepted work recast as unaccepted, and default concurrent
takeover remain forbidden. This grants no live runtime authority.
