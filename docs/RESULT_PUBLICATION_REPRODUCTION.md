# RP-013 ordinary result-publication reproduction

This is a synthetic diagnostic handoff for DEF-001, not a runtime repair or a
claim to know the historical provider race. The original
[IP-68 E-002](implementation-plan/evidence/IP-68/E-002-recorded-return-recovery.md)
separately records successful execution (expected output, exit 0, verified DONE
body/result hash) and an object still named FETCH_BALL_RETURNING over a minute
later. The defect registry also retains the owner-submitted rename-CONFLICT
telemetry. Installed binary identity and exact initiating provider/local trace
were not independently established. Prior manual recovery/recycling is not proof
that ordinary publication works; do not replay, rename or clear that old job.

## Closed diagnostic

From a development checkout with PYTHONPATH=src:

```text
python -X utf8 -m tools.experiments.result_publication --scenario all
python -X utf8 -m pytest tests/integration/test_result_publication_reproduction.py -ra
```

The experiment accepts only a fixed scenario name, never an endpoint, credential,
root, object ID, payload or replay option. It creates a synthetic in-memory wire
fixture and uses the actual GoogleDriveBackend, StateWalker, BodyKeeper and
BallPipeline. The executor returns a synthetic EXITED/0 report and starts no
process. Clock/sleep are simulated. One hard-coded fixture object, at most 256
trace entries and bounded retry policy prevent scanning or open-ended work.
Only synthetic metadata versions, lifecycle state, generation, body hashes and
normalized outcomes are emitted; no raw provider exception or private data.

The assertion-bearing suite distinguishes:

| Scenario | Injection and invariant under examination |
| --- | --- |
| baseline | Ordinary complete single execution/publication control. |
| benign-version | Metadata version advances after walker observation but before adapter precheck; body, generation, state and owner remain unchanged. |
| stale-precheck | Only the precheck's observed version is stale; actual body/state have not changed. |
| foreign-before-fence | New generation appears before the final fence read; stale publication must stop. |
| foreign-after-precheck | New generation appears after read-before-write precheck; fixture exposes absence of atomic write exclusion and post-rename identity validation. |
| http-409 / http-412 | Exact synthetic status outcomes distinguish adapter normalization from a proved ownership conflict. |
| http-429 | Rejected transient mutation followed by normal bounded retry; no repeated execution. |
| lost-reply | Rename applied but its response lost; inspect same object rather than repeat write. |
| post-apply-version-drift | Rename succeeds, then unrelated metadata changes its version; receipt equality can remain unconfirmed even with the target name visible. |
| stale-result-media | Result body write succeeds; first media read is old; verification retries reads without rewriting the result. |

Fresh fixture state and version traces must be inspected for every conclusion.
The generic CONFLICT label does not distinguish benign version movement from a
foreign owner. A successful filename read alone also does not prove identity.
These injections demonstrate current source behavior, not the original event's
probability or historical cause. The immutable reviewed evidence records actual
observed outcomes, counts and source commits after validation.

## Smallest failing invariant and RP-015 handoff

The strict expected-failure test
`test_required_invariant_same_owner_benign_metadata_change_does_not_strand_result`
preserves a valid DONE result and exactly one execution, changes only the provider
version before the final adapter precheck, and requires normal RETURNED completion.
The existing source aborts terminal publication on that conflict without fresh
reconciliation. The separate positive counterexample assertions make this
behavior visible; the marked failure is not a passed runtime acceptance check.

RP-015 must port this invariant and the negative schedules to the selected native
Docs authority and prove fresh atomic snapshot/CAS semantics. Do not add a blind
retry to the legacy non-atomic raw Drive writer. After a revision conflict, reread
the exact domain/owner/operation/generation/payload/result binding, distinguish
benign unrelated change from lost ownership, and retry only a still-authorized
transition under a new strict conditional revision within a bounded budget.
After an ambiguous reply, inspect the same transition before another mutation.
Unknown effects stay reserved. Readback must validate complete binding and result,
not only name or exact old receipt-version equality. New owner takeover never
requires all target acknowledgements, and must not replay unfinished workload.

RP-015 acceptance must replace/retire the expected-failure handoff only with
source-linked passing tests for the selected R2 implementation; retained legacy
counterexamples may remain evidence of why it is not a fallback authority.
RP-047/048 must separately prove durable result survival and ordinary publication
without manual repair. DEF-001 remains OPEN until its required repair and
end-to-end acceptance scopes pass. Historical initiating causality remains UNKNOWN
without matching original evidence, even after those repairs.

No real-provider experiment is needed to accept this bounded reproduction. If a
later exact observation is necessary, publish its separate scoped access/consent
and synthetic fixture INTENT; never reuse the old live job as a probe. Rollback
removes synthetic additions only and preserves all original failure evidence.
