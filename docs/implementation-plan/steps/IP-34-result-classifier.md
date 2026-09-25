# IP-34 - Result Classifier

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Classify trustworthy execution outcomes into DONE, PARTIAL, FAILED, or CANCELLED without confusing nonzero exit with zero side effects.

## Preconditions

IP-30 through IP-33 VERIFIED.

## Inputs / authoritative references

- `FETCH_BALL terminal semantics`

## Work

1. Define explicit ExecutionReport inputs needed for classification.
2. Implement deterministic DONE rules for completed objective signals available to RUNNER/FETCHER.
3. Implement FAILED when objective did not complete and no meaningful partial effect is known.
4. Implement PARTIAL when known side effects or completed stages exist before failure/timeout/cancel boundary.
5. Keep GONE outside classifier because it means no trustworthy result returned.
6. Allow higher-level COACH to interpret whether output satisfies user intent without rewriting factual execution classification.

## Files / modules

- `src/tb4/fetcher/result_judge.py`
- `tests/fetcher/test_result_judge.py`

## Required invariants

- Nonzero exit alone does not force FAILED if known partial work exists.
- GONE is declared by loss/recovery logic, not by a normal ExecutionReport.

## Tests

- Successful exit.
- Nonzero no effects.
- Nonzero with completed stages.
- Cancellation after side effect.
- Timeout after side effect.

## Failure cases

- Classifier guesses side effects from arbitrary stdout prose.
- PARTIAL and FAILED indistinguishable.

## Completion evidence required

- Classification matrix tests pass.

## Handoff state

FETCHER return pipeline can produce consistent terminal states.

## Amendment path

`docs/implementation-plan/amendments/IP-34/`

## Evidence path

`docs/implementation-plan/evidence/IP-34/`
