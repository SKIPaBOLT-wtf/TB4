# Checkpoint publication and cold return

`tools.development.checkpoint` prepares and validates public ledger transactions.
It never runs the recorded action, resolves deployment credentials or starts a
workload. WORK_INSTRUCTION remains the authority.

The Python `prepare` API appends one typed event, derives the cursor identity and
unsettled intents, incorporates optional manifest/evidence changes, and projects
step/index checkboxes in one candidate. It stages only public documentation and
uses RP-001 validation before returning a plan. Existing evidence is immutable;
new attempts use new paths. Source commits remain separate and must already be
public before their outcomes claim them. The current worktree is not modified.
The checkout HEAD must equal the declared public parent, with no tracked or
untracked document changes. This guard is repeated before publication: validating
stale local documents against a newer supplied ref is never sufficient. Unrelated
uncommitted source/index changes are preserved.

The CLI supports the common event-only transaction:

```text
python -m tools.development.checkpoint prepare --event <public-event.json> --branch <work-branch> --expected-head <verified-public-sha> --output <new-plan.json>
python -m tools.development.checkpoint publish --plan <plan.json> --pending <new-pending.json>
python -m tools.development.checkpoint reconcile --pending <pending.json>
python -m tools.development.checkpoint resume
```

Use a new pending path for each publication. Keep it in protected local working
storage outside tracked source, even though the helper accepts public metadata
only. Never place tokens or raw diagnostic output in event/plan/pending inputs.
The Git adapter uses existing noninteractive Git credentials and author identity;
missing credentials fail closed. It creates a temporary index and a commit tree,
never replaces the user's index/working copy and never force-pushes. Publication
requires current-ref comparison and exact remote ref/content readback. A plan is
revalidated immediately before publication, including append-only history.

## Connected GitHub equivalent

When local Git authentication is absent but an authorized GitHub connector works,
use the same validated plan: read the branch and compare expected_head; create a
tree based on that exact parent using plan.files; create a commit with that parent;
update the branch without force; read the branch and every changed file back.
Use the exact returned commit SHA, never a predicted SHA. A `Backend` implementation
can provide these operations directly. The connector's credential stays within
the connector; no token is exported to the helper or the LLM.

Keep the sanitized candidate and returned commit identity before attempting the
ref update. A request succeeding is not readback. All files form one Git commit;
separate Contents API writes are not equivalent to this atomic transaction.
This is also the documented manual fallback when the helper cannot run.

## Interrupted publication or execution

Before any provider operation the helper durably writes its public-only pending
record; after commit creation it persists the exact candidate before ref update.
Exceptions persist UNKNOWN and never echo provider errors or authorize work.
A conflict never overwrites another writer. A lost write acknowledgement is
reconciled by inspecting that exact ref and candidate's complete file contents.
Reconciliation never creates a commit, changes a ref or replays a workload.

A fresh successful INTENT publication can report RECORDED_ACTION_READY. This is
a receipt, not an executable command or an exactly-once guarantee. After any cold
return, the same intent means INSPECT_ACTION_EFFECTS even if publication succeeded:
the action may have occurred before its outcome could be saved. Check the exact
branch/run/authorized target and publish RECONCILED, OUTCOME or explicit UNKNOWN.
If remote publication is still unavailable, no new dependent action is permitted.

If the branch still equals the old expected head, report NOT_PUBLISHED and inspect
before retrying checkpoint publication. If it has moved elsewhere, inspect remote
history. Do not conflate a checkpoint retry with replaying its described action.

Rollback disables only this convenience tool. Preserve pending files and every
published journal event; continue the manual INTENT/readback/action/OUTCOME cycle.
