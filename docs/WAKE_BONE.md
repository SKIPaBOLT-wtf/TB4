# WAKE_BONE

`WAKE_BONE` is the reusable per-target request channel used by COACH to ask WATCHDOG to make a target's FETCHER ready.

It is deliberately separate from `FETCH_BALL`. Wake/bootstrap failure is a target-local result and does not automatically become `DOG_SHIT_BLOCKING`.

## Lifecycle

```text
COACH                              WATCHDOG

WAKE_BONE_READY
      |
      v
WAKE_BONE_LOADING
      |
      | write + remotely verify request body
      v
WAKE_BONE_TOSS -------------------------->
                                      claim
                                        |
                                        v
                                 WAKE_BONE_CHEW
                                   |         |
                          ready    |         | not ready
                                   v         v
                         WAKE_BONE_DONE   WAKE_BONE_FAILED
                                   \         /
                                    \       /
                                     v     v
                                  COACH consumes
                                       |
                                       v
                             WAKE_BONE_RECYCLING
                                       |
                                       v
                                WAKE_BONE_READY
```

## TOSS

`WAKE_BONE_TOSS` means the request body is complete and remotely verified.

The older draft name `WAKE_BONE_THROWN` is not protocol v1.

## CHEW

`WAKE_BONE_CHEW` means WATCHDOG owns the request.

Before any Wake-on-LAN packet, SSH bootstrap, or other target-side action, WATCHDOG must verify:

1. request schema;
2. expiry;
3. target identity.

If the request is stale, WATCHDOG must not perform WOL or SSH.

## Expired TOSS

An expired TOSS is a trustworthy failure of the wake request, not evidence that the whole control plane is broken.

WATCHDOG may terminalize it as:

```text
WAKE_BONE_TOSS -> WAKE_BONE_FAILED
reason = EXPIRED_BEFORE_CLAIM
```

No target action may occur on that path.

## DONE

Wake success means **fresh FETCHER protocol readiness**, not merely:

- a WOL packet was sent;
- the host answered ping;
- SSH connected;
- a service-start command returned zero.

The later WakeManager implementation must require a fresh target `DOG_PULSE`.

## FAILED

Examples include:

- request expired;
- target did not become reachable before wake deadline;
- FETCHER could not be started;
- target became reachable but no fresh FETCHER pulse appeared.

These remain target-local failures unless a separate control-plane invariant is broken.

## Recycling

COACH consumes DONE/FAILED evidence, moves the object to RECYCLING, clears it through the verified body helper, then publishes READY.
