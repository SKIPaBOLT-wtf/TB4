# RP-013 A001 reviewed ordinary-publication reproduction

Source: 0e10234a58ec993e9c0fb0d4893fb1f80ee2ee0e.
Test head: c1a0825b51a67e3c064a581a3f51841e3ef8a406.
Resume/ownership: a6104980e23bd88c61f36b4eef7342391e85ea08.
Existing A001 events0001/0002 were inspected, not repeated. Branch was unchanged
at a0eb0f7df1c752d7a4f3a09d2a426d6fb83e7ffe and safely fast-forwarded.
No live provider request, old job replay, real process or credential access occurred.

## Observed results and provenance
The CLI uses the real GoogleDriveBackend, StateWalker, BodyKeeper and BallPipeline
against an in-memory wire fixture, bounded fake clock and no-process executor.
Each of 11 independent schedules records one synthetic execution, exit0 and a
valid original result hash. Complete traces are in synthetic-scenario-traces.json.
Maximum trace size observed 59 events (hard limit256).
The returned synthetic elapsed time is not a real performance measurement.

| Scenario | Pipeline outcome | Final filename | Generation | Terminal wire calls |
| --- | --- | --- | --- | --- |
| baseline | RETURNED | FETCH_BALL_DONE | 7 | 1 |
| benign-version | PUBLICATION_ERROR | FETCH_BALL_RETURNING | 7 | 0 |
| stale-precheck | PUBLICATION_ERROR | FETCH_BALL_RETURNING | 7 | 0 |
| foreign-before-fence | STALE | FETCH_BALL_RETURNING | 8 | 0 |
| foreign-after-precheck | RETURNED | FETCH_BALL_DONE | 8 | 1 |
| http-409 | PUBLICATION_ERROR | FETCH_BALL_RETURNING | 7 | 1 |
| http-412 | PUBLICATION_ERROR | FETCH_BALL_RETURNING | 7 | 1 |
| http-429 | RETURNED | FETCH_BALL_DONE | 7 | 2 |
| lost-reply | RETURNED | FETCH_BALL_DONE | 7 | 1 |
| post-apply-version-drift | PUBLICATION_ERROR | FETCH_BALL_DONE | 7 | 1 |
| stale-result-media | RETURNED | FETCH_BALL_DONE | 7 | 1 |

The original result remains byte-identical except the two deliberately injected
foreign-generation schedules. In those two, original result hash validity refers
to the retained result before the injected foreign mutation, not the changed body.
No passing counterexample assertion is a claim that the observed legacy behavior
is safe.

## C1: historical fact versus acceptance
E-002 records expected output, exit0, DONE/EXIT_ZERO/KNOWN and verified payload/result
hashes, while independent reads still found RETURNING over one minute later.
The registry separately retains owner rename-CONFLICT telemetry. Installed binary
identity and initiating provider trace were not independently established. Manual
repair and later recycling are not ordinary round-trip acceptance.
The new fixture independently reproduces successful execution plus publication
failure. Historical causality stays UNKNOWN, proven_origin remains null.

## C2: controlled version/media/provider schedules
Benign metadata changes version5 to6 before adapter precheck; stale-precheck returns
version4 when the walker's expected version is5. Both retain generation7 and the
exact result, normalize to CONFLICT, abort STATE_CONFLICT with zero confirmation
probes and send zero terminal writes. One same-identity metadata change is enough
to strand this current-source path.
A stale first result-media read instead recovers without repeating the body write.
Lost rename response recovers by one write and same-object readback. HTTP429 is
a rejected mutation then bounded retry, not repeated execution.

## C3: proved paths and retained rejected hypotheses
- SUPPORTED only for this fixture: read-before-write version mismatch is treated
  as terminal STATE_CONFLICT without fresh logical-owner reconciliation.
- SUPPORTED: a foreign generation visible before the fence stops as STALE with
  no terminal write; a foreign generation arriving after precheck can still be
  renamed DONE and reported RETURNED because the actual write has no atomic
  version predicate and confirmation checks name/version, not fresh full binding.
- FAILED in the tested bounded schedule: stale media alone necessarily strands
  the ordinary result; the existing BodyKeeper retries reads and completes here.
- FAILED in the tested bounded schedule: lost mutation reply necessarily requires
  a second write; existing readback completes with one wire call.
- SUPPORTED: synthetic HTTP409 becomes CONFLICT/STATE_CONFLICT, HTTP412 becomes
  AMBIGUOUS/UNCONFIRMED, not a proved logical-owner conflict. No evidence says the
  historical provider returned either status.
- SUPPORTED: a post-success benign version increase6 to7 keeps nameDONE but exact
  receipt-version comparison ends UNCONFIRMED after four probes, without replay.
- UNTESTED historical hypothesis: which, if any, schedule caused E-002. These
  fixtures cannot identify that missing real trace retrospectively.

## C4: failing oracle and safe repair handoff
The strict xfail test_required_invariant_same_owner_benign_metadata_change_does_not_strand_result
fails exactly at required RETURNED versus actual PUBLICATION_ERROR, after proving
unchanged result and exactly one execution. It is an intentionally failing RP-015
handoff, not a passed runtime gate. A future unexpected pass fails strict xfail
and requires evidence review.
RP-015 must qualify the selected native Docs atomic authority under the same
schedules, not add a blind retry to raw Drive. Verify fresh owner/operation/
generation/payload/result binding and strict CAS for each bounded retry; inspect
ambiguous effects; never replay work or wait for every target during owner takeover.
RP-047/048 and end-to-end scopes remain required. DEF-001 stays OPEN.

## Validation
Windows Python3.11 with process-local venv resolver/UTF-8 and fresh task-local temp:
python -X utf8 -m tools.experiments.result_publication --scenario all
Exit0; all11 complete bounded traces inspected.
python -X utf8 -m pytest tests/integration/test_result_publication_reproduction.py tests/integration/test_google_transactions.py tests/drive tests/fetcher tests/feasibility tests/protocol tests/development --basetemp <new-task-local-directory> -ra --tb=short
868 passed, 2 skipped, 1 expected failure in25.02s, exit0.
871 exact nodes collected in0.35s, preserved in local-collected-nodes.txt.
Skipped cases: test_google_client.py:122 POSIX mode; test_cancellation.py:258
POSIX SIGTERM-ignore. Neither is a passing Windows capability claim.
27 new cases:26 passing specification/control assertions and one strict xfail.
Linux CI36791123130/job110144004187:1285 passed,2 skipped,1 xfailed in17.34s.
Progress36791123026/job110144003708: all checks pass.
Local UTF-8 ledger --base a6104980e23bd88c61f36b4eef7342391e85ea08:
PASS,12 prior verified, sole pending INTENT0005. Scanner clean; diff and exact
test-head source equality exit0. Native Desktop workflow paths are unchanged;
no installer rebuild was required or requested for this diagnostic-only addition.

## Review, privacy, compatibility and rollback
Source inspection confirms no credential/client construction, external endpoint,
subprocess or arbitrary CLI target. Fixed synthetic identifiers/body hashes only.
Trace sizes bounded; command input cannot redirect the diagnostic to a deployment.
Actual runtime source/protocol/packaging unchanged. Earlier published history intact.
Rollback removes synthetic additions only; retain the original result/archives and
unknown effects. No model/test proves native Docs production safety or historical
root cause. This accepts reproducibility and handoff, not resolution of DEF-001.
