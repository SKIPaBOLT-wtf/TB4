# FETCH_BALL

`FETCH_BALL` is the single reusable work channel for one target device in TB4 protocol v1.

Its Google Drive file ID remains stable while the filename changes to express lifecycle state.

## Main flow

```text
COACH                         FETCHER / WATCHDOG

FETCH_BALL_READY
       |
       | reserve
       v
FETCH_BALL_LOADING
       |
       | write complete request body
       | remote readback + verify
       v
FETCH_BALL_TOSS ---------------------------->
                                      claim
                                        |
                                        v
                                 FETCH_BALL_CHEW
                                        |
                                  local execution
                                        |
                                        v
                              FETCH_BALL_RETURNING
                                        |
                                  write result body
                                  remote verify
                                        |
                         +--------------+--------------+
                         |              |              |
                         v              v              v
                       DONE          PARTIAL         FAILED
                         |              |              |
                         +-------+------+-------+------+
                                 |              |
                            CANCELLED          GONE
                                 |              |
                                 +------+-------+
                                        |
                                  COACH consumes
                                        |
                                        v
                              FETCH_BALL_RECYCLING
                                        |
                                clear/verify body
                                        |
                                        v
                               FETCH_BALL_READY
```

The diagram is conceptual. Exact legal edges and actors are authoritative in `protocol/state-machines.yaml`.

## Why TOSS and CHEW

The protocol intentionally uses:

- `FETCH_BALL_TOSS` rather than older draft `FETCH_BALL_THROWN`;
- `FETCH_BALL_CHEW` rather than older draft `FETCH_BALL_CHEWING`.

These names are canonical protocol v1 vocabulary.

## State ownership

### READY

No job is active. COACH may reserve the stable object by transitioning it to LOADING.

### LOADING

COACH owns the channel. Only in this state may COACH write the request body.

The intended sequence is:

```text
READY -> LOADING
confirm remote name
write complete body
read body back
verify schema/hash
LOADING -> TOSS
confirm remote name
```

If the request cannot be published safely, COACH may move LOADING to RECYCLING and clear it rather than exposing a half-written job.

### TOSS

The request body is complete and verified. FETCHER may claim it only if expiry, schema, job identity, and generation checks pass.

An expired request that was never claimed may be terminalized by WATCHDOG through RETURNING -> FAILED. It must not execute late.

### CHEW

FETCHER has claimed the exact generation. Local execution may now begin.

FETCHER may write bounded execution-start evidence only after CHEW is remotely confirmed.

If FETCHER disappears beyond the later-defined stale/grace rules, WATCHDOG may move CHEW to GONE.

### RETURNING

A terminal report is being written and verified before the normal terminal state is published.

FETCHER normally owns this state. WATCHDOG may use it for a verified infrastructure result such as a request that expired without ever being claimed.

### DONE

A trustworthy report says execution completed successfully.

### PARTIAL

A trustworthy report exists, but meaningful work occurred before the requested operation fully completed.

A non-zero exit code alone does not decide PARTIAL. Later result-classification rules must use explicit execution evidence.

### FAILED

A trustworthy terminal result exists, and no meaningful partial effect is known.

### CANCELLED

Execution was intentionally interrupted. The terminal body must still preserve known effects and output evidence.

### GONE

No trustworthy execution result returned. Side effects may be unknown.

`GONE` is deliberately different from `FAILED`: a mutating GONE job must be inspected before any replay.

### RECYCLING

COACH has consumed the terminal evidence. The body may now be cleared/reinitialized for the next generation. READY is published only after that cleanup is verified.

## Idempotency

A verified helper may treat a requested transition as idempotently complete when the exact stable object is already at the intended target state **and** the operation fence still identifies the same job/generation.

Same filename alone is never enough to prove ownership.

## Body mutation rule

Body writers are specified per state in `protocol/state-machines.yaml`.

No actor may write a dependent body change until the state transition granting that ownership has been remotely confirmed.

## Replay rule

- DONE: never replay implicitly.
- PARTIAL: inspect known effects first.
- FAILED: a retry is a new explicit generation.
- CANCELLED: a retry is a new explicit generation.
- GONE: inspect effects before any retry.

This rule is especially important for mutating scripts where a lost result does not imply that nothing happened.
