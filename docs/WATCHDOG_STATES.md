# WATCHDOG Control States

WATCHDOG has two independent logical concepts:

1. **activity mode** — how aggressively it schedules local checks;
2. **global control-plane fault** — whether it can safely accept/progress normal TB4 control work.

Do not merge them.

## DOG_SNOOZE / DOG_AWAKE

```text
DOG_SNOOZE
    |
    | active work / event
    v
DOG_AWAKE
    |
    | no work + awake lease expired
    v
DOG_SNOOZE
```

These names are the canonical filenames for the `WATCHDOG_MODE` logical object.

### DOG_SNOOZE

The dog is healthy. It is simply using low-frequency idle cadence.

SNOOZE is **not**:

- offline;
- failed;
- blocked;
- proof that a target is unavailable.

### DOG_AWAKE

The dog has active work or an active responsiveness lease.

Typical awake triggers include:

- a WAKE_BONE operation;
- active FETCH_BALL monitoring;
- tree repair;
- explicit local maintenance.

Mode changes are owned by WATCHDOG itself. COACH does not need a separate DOG_WHISTLE object in protocol v1.

## DOG_SHIT

`DOG_SHIT` is one global fault register, not a log and not a generic error bucket.

```text
DOG_SHIT_CLEAN
       |
       | global control invariant fails
       v
DOG_SHIT_BLOCKING
       |
       | COACH reads / acknowledges
       v
DOG_SHIT_REVIEWED
       |
       +---- invariant still broken ----> DOG_SHIT_BLOCKING
       |
       +---- invariant revalidated -----> DOG_SHIT_CLEAN
```

### DOG_SHIT_CLEAN

Normal global state. WATCHDOG may accept/progress normal work.

### DOG_SHIT_BLOCKING

WATCHDOG no longer trusts the control plane enough to accept/progress new normal work.

Only the current global blocking fault is stored. This is deliberately **not** an append-only giant error log.

Normal new control work stops, but diagnostic reads and the bounded repair actions needed to recover remain allowed.

### DOG_SHIT_REVIEWED

COACH has read and acknowledged the fault.

REVIEWED is **not** the same as repaired.

WATCHDOG must independently revalidate the failed invariant before transitioning to CLEAN. If the invariant is still broken, it returns to BLOCKING.

## Blocking examples

Examples that may justify DOG_SHIT_BLOCKING after their own bounded retry/reconciliation policy is exhausted:

- persistent loss of the configured Drive root;
- irreducibly ambiguous PARK_MAP;
- irreducibly ambiguous canonical live tree;
- inability to confirm verified state mutation semantics;
- WATCHDOG Drive authorization unavailable;
- clock error large enough to make TTL decisions unsafe.

## Explicitly not DOG_SHIT

These are scoped elsewhere:

- one target offline;
- WOL failure;
- SSH bootstrap failure;
- one FETCH_BALL_FAILED;
- one FETCH_BALL_PARTIAL;
- one FETCH_BALL_GONE;
- one WAKE_BONE_FAILED.

A sick player does not mean the dog park itself is on fire.

## DOG_PULSE

DOG_PULSE is heartbeat evidence, not the activity-mode object and not the fault object.

Later schemas/timing rules define freshness. A stale pulse may be evidence used by another participant, but filenames `DOG_SNOOZE` / `DOG_AWAKE` remain independent from pulse data.
