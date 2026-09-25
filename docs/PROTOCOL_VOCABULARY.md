# TB4 Protocol Vocabulary

TB4 deliberately uses a dog/ball vocabulary. The names are mnemonic protocol language, not decoration.

Once a name is present in `protocol/objects.yaml`, changing it is a protocol migration rather than a cosmetic refactor.

## Roles

### COACH

The AI-facing orchestrator. COACH decides **what** work should happen and interprets returned evidence. It does not implement Drive retry loops, LAN discovery, or local process execution.

### WATCHDOG

The LAN coordinator. WATCHDOG observes known devices, discovers strays, performs wake/bootstrap, audits and repairs the deterministic Drive tree, performs retention, and owns global blocking health.

WATCHDOG does not become a generic remote shell.

### FETCHER

The target-side agent. FETCHER claims its own work channel, coordinates RUNNER, emits heartbeat evidence, handles cancellation, returns results, and may exit after a configured idle period.

### RUNNER

The deliberately boring local process executor. RUNNER executes local commands/scripts and captures process evidence. It never changes Drive protocol state directly.

## Canonical directories

- `GENESIS` — reconstructable canonical bootstrap metadata.
- `SETTINGS` — public-safe runtime settings.
- `DOG_HOUSE` — WATCHDOG control objects.
- `BALL_PARK` — deterministic per-device trees.
- `KENNEL` — a device's wake/bootstrap channel.
- `PLAYGROUND` — a device's active work/cancel channels.
- `TOY_BOX` — bounded request/result artifacts.
- `BONEYARD` — short-lived terminal history.
- `STRAY_YARD` — observed but unregistered devices.
- `DOG_POUND` — quarantine for ambiguous, duplicate, or malformed objects.

## Fixed logical objects

- `START_HERE`
- `PARK_MAP`
- `DOG_TAG`
- `DOG_PULSE`
- `DOG_SNIFF`

Their names remain deterministic. Their bodies may change according to later schemas.

## Stateful logical objects

### FETCH_BALL

Canonical active filenames are produced from the root plus state:

```text
FETCH_BALL_READY
FETCH_BALL_LOADING
FETCH_BALL_TOSS
FETCH_BALL_CHEW
FETCH_BALL_RETURNING
FETCH_BALL_DONE
FETCH_BALL_PARTIAL
FETCH_BALL_FAILED
FETCH_BALL_CANCELLED
FETCH_BALL_GONE
FETCH_BALL_RECYCLING
```

### WAKE_BONE

```text
WAKE_BONE_READY
WAKE_BONE_LOADING
WAKE_BONE_TOSS
WAKE_BONE_CHEW
WAKE_BONE_DONE
WAKE_BONE_FAILED
WAKE_BONE_RECYCLING
```

### STOP_BALL

```text
STOP_BALL_READY
STOP_BALL_LOADING
STOP_BALL_REQUESTED
STOP_BALL_RETURNING
STOP_BALL_ACKNOWLEDGED
STOP_BALL_RECYCLING
```

### WATCHDOG mode

This deliberately uses the shorter dog wording:

```text
DOG_SNOOZE
DOG_AWAKE
```

### Global WATCHDOG/control-plane fault

```text
DOG_SHIT_CLEAN
DOG_SHIT_BLOCKING
DOG_SHIT_REVIEWED
```

`DOG_SHIT` is **not** a general error bucket. A target being offline, a wake failing, a command returning non-zero, or one work result being lost does not by itself create `DOG_SHIT_BLOCKING`.

## Naming invariants

1. Active control names are deterministic.
2. No active control filename contains a timestamp, UUID, random suffix, hostname, or generation number.
3. Runtime identity lives in the stable Drive object ID and body fencing fields, not in a constantly changing filename.
4. Dynamic names are allowed in history/artifact areas where they are not used as the live control path.
5. Old draft terminology must not remain as an active alias.

## Historical draft names that are intentionally rejected

These appeared during design and are **not** canonical protocol names:

- `WAKE_BONE_THROWN` -> use `WAKE_BONE_TOSS`
- `FETCH_BALL_THROWN` -> use `FETCH_BALL_TOSS`
- `FETCH_BALL_CHEWING` -> use `FETCH_BALL_CHEW`
- `DOG_MODE_NAPPING` -> use `DOG_SNOOZE`

Do not accept both spellings in protocol v1 merely for convenience. If compatibility is ever required, implement an explicit migration.


## Target-local LEASH state

```text
LEASH_CLEAR
LEASH_TANGLED
```

This is a per-target infrastructure state. It must never be treated as an alias for the global `DOG_SHIT` register.
