# TB4 COACH Interface

> Historical v1 runtime reference. New instruction selection starts at
> `skill/tb4/SKILL.md` and its pinned compatibility catalog. This manual is not
> an R2 operational profile or a fallback when no compatible release exists.

COACH is the AI-side decision layer. It turns a user goal into a small number of deterministic TB4 control-plane operations.

COACH does **not** replace WATCHDOG, FETCHER, RUNNER, or the protocol validators.

## Responsibility boundary

```text
USER INTENT
    |
    v
  COACH
    |
    | chooses target / job / timing / next branch
    v
Google Drive canonical objects
    |
    +-------------> WATCHDOG
    |                 |
    |                 +-- LAN / WOL / fixed SSH bootstrap
    |
    +-------------> FETCHER
                      |
                      +-- RUNNER
```

COACH owns:

- target selection;
- work intent and payload construction;
- selection of an allowed run limit;
- interpretation of terminal result evidence;
- whether a new explicit generation is justified;
- planning independent next work while another target is busy.

COACH must not own:

- LAN discovery;
- arbitrary SSH command execution;
- local subprocess lifecycle;
- Drive retry loops already encoded in deterministic helpers;
- WATCHDOG fault classification;
- invented state transitions.

## Cold-start source loading

Do not load the whole repository into context.

```text
docs/START_HERE.md
        |
        v
docs/COACH.md
        |
        +--> protocol/state-machines.yaml     when a transition matters
        +--> protocol/schemas/...             when a body is built/read
        +--> config/defaults.toml             when timing/rate matters
        +--> docs/<specific topic>.md         when deeper explanation is needed
```

For live state:

```text
selected TB4 Drive root
        |
        v
START_HERE
        |
        v
PARK_MAP
        |
        v
exact stable object IDs
```

The normal path should not enumerate target folders after the required exact IDs are known.

## Preflight flow

```text
user asks for target work
        |
        v
resolve target from PARK_MAP
        |
        v
read DOG_SHIT exact object
        |
        +-- BLOCKING --> diagnostics/repair only
        |
        v
read target DOG_SNIFF / DOG_PULSE as needed
        |
        v
is FETCHER fresh?
     /      \
   yes       no
    |         |
    |         v
    |     WAKE_BONE workflow
    |         |
    |     fresh DOG_PULSE?
    |         |
    +---------+
        |
        v
inspect FETCH_BALL exact object
        |
        +-- READY --> dispatch allowed
        |
        +-- terminal --> consume/reconcile before recycle
        |
        +-- active --> observe current job; do not overwrite
        |
        +-- unexpected --> read canonical state machine; fail closed
```

## Job construction

Use the canonical FETCH_BALL schema.

Every new job has a new explicit operation/job identity and generation.

Choose `run_limit_s` based on expected work:

- short inspection: small limit;
- package/filesystem work: larger limit;
- long operation: explicitly larger limit;
- never exceed canonical maximum policy.

The exact default and maximum are configuration, not Skill constants.

### Payload choice

```text
small simple command
       |
       +--> inline payload

multiline / large / structured script
       |
       +--> TOY_BOX artifact
              |
              +-- size
              +-- SHA-256
              +-- interpreter allowlist
              +-- expiry
              +-- verified local materialization
```

Never convert a large script into one enormous SSH command line.

SSH is limited to fixed FETCHER service bootstrap.

## FETCH_BALL publication

COACH follows only canonical transitions. Conceptually:

```text
FETCH_BALL_READY
      |
      | reserve
      v
FETCH_BALL_LOADING
      |
      | write complete body
      | remote verify
      v
FETCH_BALL_TOSS
```

The filename/state is authoritative lifecycle state. The body is authoritative operation identity and evidence.

If body verification or state confirmation is ambiguous, reconcile that same operation. Do not create a duplicate request.

## Waiting and progress planning

COACH should not spend reasoning tokens asking the same unchanged object for status.

After TOSS:

1. load relevant timing values;
2. calculate earliest useful recheck;
3. identify deadline/stale conditions;
4. pre-plan terminal branches;
5. continue independent reasoning or other targets.

When a host supports a watcher/sub-agent, delegate a bounded watch contract:

```text
object_id: exact stable ID
current operation_id/generation: exact values
terminal states: canonical expected states
earliest_check: derived from timing
deadline: derived from request/runtime policy
report_on: state change or deadline
folder_scan: forbidden
```

The watcher must not decide what a PARTIAL/GONE result means for the user's objective. That remains COACH work.

If the hosting environment cannot truly monitor in the background, do not claim that it can. Recheck during the active operation only when useful.

## Result branches

```text
FETCH_BALL terminal
    |
    +-- DONE ------> consume result -> plan next objective
    |
    +-- PARTIAL ---> inspect completed effects -> continue only remaining work
    |
    +-- FAILED ----> inspect reason -> optional NEW generation
    |
    +-- CANCELLED -> consume known evidence -> optional NEW generation
    |
    +-- GONE ------> effects may be unknown
                         |
                         +-- read-only proven no effect? -> new generation may be safe
                         |
                         +-- mutating/unknown -----------> inspect target first
```

Exit code alone never overrides canonical result classification.

## Recycling

Do not recycle merely because a terminal filename exists.

First consume or reconcile terminal evidence.

Then use the canonical COACH terminal -> RECYCLING -> READY transitions and verified body clearing.

A GONE job requires explicit unknown-effect review before COACH recycles it.

## Cancellation

STOP_BALL is bound to the exact current FETCH_BALL identity.

COACH must supply the schema-required:

- FETCH_BALL object ID;
- job/operation identity;
- generation.

A stale cancellation must not affect a newer generation.

## WATCHDOG blocking fault

`DOG_SHIT_BLOCKING` means the control plane cannot safely progress normal work.

Allowed while blocking:

- diagnostic reads;
- documented repair actions.

Not allowed:

- new normal control work;
- clearing the fault because it was merely acknowledged.

COACH may transition BLOCKING -> REVIEWED according to the canonical state machine. WATCHDOG clears it only after revalidating the failed invariant.

## Target-local problems

One target being offline, one failed wake, one PARTIAL/GONE job, or one target infrastructure problem is not automatically a global DOG_SHIT.

Use canonical target-local health state and result evidence.

## Privacy and credentials

COACH never puts credential material in Drive objects.

Opaque local references may identify locally configured credentials where the protocol permits, but backing passwords/tokens/keys remain local.

Never commit private deployment root IDs, private addresses, or private topology to this public repository.

## Portable operation

The Skill is intentionally small. Another AI should be able to learn the current TB4 behavior by following:

```text
Skill
  -> START_HERE
  -> COACH
  -> machine-readable protocol/config
  -> live PARK_MAP
```

This avoids embedding a stale second copy of the full protocol inside an AI prompt.
