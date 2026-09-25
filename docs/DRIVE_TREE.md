# TB4 Drive Tree

This document describes the protocol-v1 persistent tree. The machine-readable authority is `protocol/tree-blueprint.yaml`.

## Top-level tree

```text
TB4-LLM-EXCHANGE/                 // configured root; NEVER auto-recreated elsewhere
│
├── START_HERE                    // remote protocol entrypoint
├── PARK_MAP                      // logical object -> stable Drive ID map
│
├── GENESIS/                      // canonical bootstrap metadata
├── SETTINGS/                     // runtime settings; private values are external
│
├── DOG_HOUSE/                    // active WATCHDOG control plane
│   ├── DOG_TAG
│   ├── DOG_PULSE
│   ├── DOG_SNOOZE | DOG_AWAKE
│   └── DOG_SHIT_CLEAN | DOG_SHIT_BLOCKING | DOG_SHIT_REVIEWED
│
├── BALL_PARK/                    // one independent work thread per registered device
│   └── <device_key>/
│       ├── DOG_TAG
│       ├── DOG_SNIFF
│       ├── DOG_PULSE
│       ├── LEASH_CLEAR | LEASH_TANGLED
│       │
│       ├── KENNEL/
│       │   └── WAKE_BONE_<STATE>
│       │
│       ├── PLAYGROUND/
│       │   ├── FETCH_BALL_<STATE>
│       │   └── STOP_BALL_<STATE>
│       │
│       ├── TOY_BOX/              // scripts / large results; not live state
│       └── BONEYARD/             // short history; not live state
│
├── STRAY_YARD/                   // observed, not registered/authorized targets
└── DOG_POUND/                    // quarantine; never a silent trash can
```

## Root identity

The root is supplied explicitly by deployment configuration.

If that configured root disappears or becomes inaccessible, TB4 stops/reports a blocking problem. It must not create a new root somewhere convenient, because that could create two independent control planes.

## PARK_MAP

Normal runtime should use stable Drive IDs from `PARK_MAP`.

The expected normal path is:

```text
logical target/object
      |
      v
PARK_MAP cached stable ID
      |
      v
exact object metadata/body operation
```

not:

```text
list folder
-> search names
-> choose a plausible object
```

Folder enumeration belongs to bootstrap, audit, discovery, repair, migration, and diagnostics.

## Device folder key

`BALL_PARK/<device_key>/` is stable after registration.

Initial assignment preference:

1. explicit stable alias;
2. unique normalized hostname seen at registration;
3. generated stable identity fragment.

A later hostname change updates DOG_TAG metadata if appropriate. It does **not** automatically rename the registered device folder.

This preserves human-readable names when useful without treating a mutable hostname as identity.

## Exactly one work channel per device

Protocol v1 intentionally supports:

```text
one FETCH_BALL
one STOP_BALL
one WAKE_BONE
```

per registered target.

Different targets can work independently and concurrently.

Concurrency within one target can be added in a later protocol version by adding explicit work-lane identity rather than duplicating v1 objects ad hoc.

## Repair policy

Every blueprint node declares how it may be repaired.

Examples:

- a missing static folder under a verified parent can be recreated;
- an empty heartbeat object can be seeded safely;
- DOG_TAG identity must not be invented;
- PARK_MAP can be rebuilt only if the observed tree is unambiguous;
- the configured root is never auto-created elsewhere.

Duplicates and malformed ambiguous objects are preserved in `DOG_POUND`, not silently deleted.

## TOY_BOX and BONEYARD

These are deliberately outside the live control path.

Dynamic artifact/history names are allowed there because normal protocol decisions do not depend on discovering “the newest file” by scanning those directories.
