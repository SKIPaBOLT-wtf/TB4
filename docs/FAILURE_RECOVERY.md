# TB4 Failure Recovery

This document maps deliberate failure-injection scenarios to the expected deterministic TB4 outcome.

The rule is simple:

```text
observe
  -> preserve authoritative state
  -> reconcile
  -> recover or block explicitly
```

Never:

```text
guess
  -> replay mutating work
  -> hope
```

## 1. FETCHER disappears during FETCH_BALL_CHEW

Expected behavior:

```text
FETCH_BALL_CHEW
    |
    | FETCHER becomes unrecoverably stale/lost
    v
FETCH_BALL_GONE
```

`GONE` means no trustworthy terminal result returned. The job must not be blindly replayed, especially when the payload can mutate the target.

Recovery:

1. preserve the original job body;
2. inspect target state if the payload was mutating;
3. decide whether to continue, repair, or issue a new generation;
4. recycle only after the result has been consumed/reconciled.

## 2. Stale worker returns after a newer generation exists

A stale worker may observe the same stable Drive object ID, but it no longer owns the generation.

Required fence:

```text
object_id
+ operation_id
+ generation
+ expected state
```

If any ownership component is stale, the mutation is rejected. The stale worker exits without modifying the newer job.

## 3. Delayed or ambiguous Drive mutation response

An ambiguous mutation is not treated as automatic failure.

```text
mutation request
    |
    | response ambiguous / visibility delayed
    v
read exact object ID
    |
    +--> target state/body visible -> idempotent success
    |
    +--> old state still visible -> bounded retry/reconciliation
    |
    +--> irreconcilable -> explicit UNCONFIRMED/blocking path
```

Never create a second logical operation merely because the first response was ambiguous.

## 4. Duplicate live control object

`PARK_MAP` identifies the canonical object.

During maintenance audit:

1. preserve the canonical stable object ID;
2. quarantine the duplicate under `DOG_POUND`;
3. store provenance for the quarantined object;
4. continue only if canonical identity remains unambiguous.

If canonical identity itself is ambiguous, repair blocks instead of guessing.

## 5. Corrupted live control body

A malformed or schema-invalid body must be rejected before execution ownership is claimed.

Example:

```text
FETCH_BALL_TOSS
    |
    | invalid body
    v
remain FETCH_BALL_TOSS
    |
    +--> diagnostic / repair required
```

The executor must not run a payload that did not pass schema and integrity checks.

## 6. Drive disconnect during active control work

If the backend becomes unavailable before claim/verified mutation, the current authoritative state is preserved.

Example:

```text
FETCH_BALL_TOSS
    |
    | Drive read fails
    v
FETCH_BALL_TOSS
```

No speculative terminal result is published.

A recoverable transport fault stays transport-scoped. A persistent inability to access the canonical control plane may promote to a WATCHDOG blocking fault.

## 7. Unsafe wall-clock skew

TTL and freshness logic depends on sufficiently sane wall clocks.

If observed skew exceeds configured tolerance:

```text
clock validation
    |
    v
CLOCK_UNSAFE_FOR_TTL
    |
    v
DOG_SHIT_BLOCKING
```

Normal control work is blocked because job expiry and freshness decisions are no longer trustworthy.

Monotonic clocks remain the authority for local elapsed-time deadlines.

## 8. Interrupted bootstrap or tree repair

Bootstrap never invents another TB4 root.

If bootstrap stops after creating only part of the canonical child tree, the next bootstrap run:

1. reuses matching existing canonical children;
2. creates only missing safe children;
3. rejects duplicates/ambiguity;
4. produces one canonical tree;
5. does not duplicate already-created children.

Unsafe or ambiguous reconstruction blocks.

## 9. Oversized output and artifact failure

Large output must not inflate the live FETCH_BALL object.

Expected path:

```text
RUNNER output
    |
    +--> within inline limit -> bounded inline result
    |
    +--> larger -> TOY_BOX result artifact
                       |
                       +--> verified artifact -> reference result
                       |
                       +--> artifact cannot be safely created
                               -> explicit artifact failure
                               -> no false artifact reference
```

Temporary local spool data must be cleaned according to failure policy.

## Replay rule

Automatic replay is safe only when TB4 can prove the prior operation had no mutating effect or never began.

```text
known no effect -> retry may be allowed
known partial effect -> inspect/reconcile first
unknown effect -> inspect/reconcile first
```

`FETCH_BALL_GONE` is intentionally not equivalent to `FETCH_BALL_FAILED`.

## Failure-injection coverage

The integrated scenarios live under:

`tests/failure_injection/`

The suite deliberately validates final safe state or blocking state, not merely that an exception was raised.
