# STOP_BALL

`STOP_BALL` is the reusable cancellation request channel for one target.

It never identifies work merely by target name or by the current FETCH_BALL filename. A cancellation request must fence itself to the exact active work generation.

## Safe publication lifecycle

```text
COACH                                  FETCHER

STOP_BALL_READY
      |
      v
STOP_BALL_LOADING
      |
      | write + remotely verify:
      |   fetch_ball_object_id
      |   job_id
      |   generation
      v
STOP_BALL_REQUESTED ------------------------>
                                            |
                                  verify exact match
                                            |
                                            v
                                  STOP_BALL_RETURNING
                                            |
                                      write + verify
                                   acknowledgement body
                                            |
                                            v
                               STOP_BALL_ACKNOWLEDGED
                                            |
                                   COACH consumes ack
                                            |
                                            v
                                STOP_BALL_RECYCLING
                                            |
                                            v
                                    STOP_BALL_READY
```

The staging states are intentional. The earlier three-state draft was rejected because it could expose a state before the corresponding body write was remotely complete.

## Request matching

FETCHER may act on a REQUESTED cancel only when all of these identify the current active work:

- stable FETCH_BALL Drive object ID;
- `job_id`;
- `generation`.

Any mismatch means **do not cancel**.

A stale STOP_BALL must never terminate a newer job that happens to reuse the same FETCH_BALL object.

## Cancellation result ownership

STOP_BALL only carries the request and acknowledgement that the cancellation instruction was handled.

The actual execution outcome remains on FETCH_BALL:

```text
FETCH_BALL_RETURNING
    -> FETCH_BALL_CANCELLED
```

That result must preserve any known partial side effects, stdout/stderr evidence, and exit/termination information.

## Expired or obsolete request

If STOP_BALL remains REQUESTED but the referenced FETCH_BALL generation is already terminal or the cancel request has expired, COACH may attempt:

```text
STOP_BALL_REQUESTED -> STOP_BALL_RECYCLING
```

through the verified state helper.

If FETCHER has already claimed the request into RETURNING, that COACH transition must fail as a normal state conflict. This prevents a race from clearing an in-flight acknowledgement.

## Why no giant cancellation command

STOP_BALL is a protocol object, not a remote shell command. FETCHER performs local process-tree cancellation through RUNNER. SSH is never used to inject a cancellation script into a target job.
