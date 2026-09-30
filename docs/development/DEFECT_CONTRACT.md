# Defect provenance and revalidation (RP-003)

`revisions/R2/defects.yaml` is a typed public index, validated with the ledger.
Detection location, suspected source and proven source are separate. Null means
unknown. Proven origin needs linked evidence; validation cannot replace review of
causality. Reproduction carries failing/passing source commits independently of
origin. Requirements describe affected scope, not demonstrated implementation.

Schema 2 migration maps v1 `required_acceptance` to `affected_acceptance`, keeps
source guesses suspected, and preserves missing proof as null. Every original
record is retained as canonical JSON in immutable `legacy_record`, including old
reproduction-step, rule, resolution and observation fields. No old resolved record
is retroactively treated as a new repair. DEF-001/002 remain OPEN with no invented
origin, no passing SHA and no new runtime observation. Issue #7 was read as OPEN;
its state is not an acceptance input. Original IP-68 evidence stays immutable.

Use `tools.development.defects.open_repair` to create a candidate for a previously
accepted responsible step. It snapshots accepted attempt/check/receipt/build
references, advances attempts, clears current checks, and lists required rechecks.
Transitive dependents and explicitly affected acceptances are held; never-started
steps remain planned. Concurrent in-progress work requires reconciliation instead
of silently taking ownership. Publish the candidate and matching new-attempt
INTENT together using `checkpoint.prepare(..., manifest=..., defects=...)`, then
the normal publish/readback gate. A candidate is not authorization to execute.

Append hypotheses with stable IDs. Failed claims remain; a later experiment gets
a new record rather than rewriting a failed one. Repair entries also remain
immutable. Rechecks must pass with reviewed receipts on the later active attempt
and dependencies must again be VERIFIED. Issue closure, clearing a recheck list,
old receipts or restored old status cannot release the hold. New resolutions need
a regression test, passing source, resolution evidence and accepted listed work.

History validation and checkpoint publication preserve journals, acceptance
snapshots, hypotheses, repair linkage and existing evidence bytes. Rollback means
a corrective event and reviewed source change, not deleting a defect or restoring
acceptance from an old build. Helpers operate only on public development data;
they do not run workloads, contact devices or resolve live pilot symptoms.
