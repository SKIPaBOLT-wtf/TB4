# Device Observation and Local Fault Semantics

TB4 keeps device identity, LAN observation, FETCHER readiness, and target-local infrastructure faults as separate concepts.

## DOG_TAG — who/what the target is

`DOG_TAG` is the stable declaration of a target and its capabilities.

Examples of capability facts:

- Wake-on-LAN can be attempted;
- SSH bootstrap is configured;
- FETCHER may exit when idle;
- OS family/interpreter support.

A capability means **the feature may be attempted**. It does not mean the device is currently online.

Hostname is useful metadata but is not the canonical TB4 device identity by itself, because hostnames can change.

## DOG_SNIFF — what WATCHDOG sees on the LAN

`DOG_SNIFF` is WATCHDOG's current network observation.

Conceptual reachability values:

```text
ONLINE
OFFLINE
UNKNOWN
```

A local probe may run frequently, but unchanged observations should not be rewritten to Drive every time. WATCHDOG publishes on meaningful change and periodically refreshes unchanged evidence for freshness.

DOG_SNIFF online does **not** prove FETCHER is ready.

## DOG_PULSE — whether FETCHER is alive

A fresh `DOG_PULSE` is the strongest normal readiness evidence for FETCHER.

A target can therefore be:

```text
DOG_SNIFF = ONLINE
DOG_PULSE = STALE
=> host online, FETCHER not ready
```

or:

```text
DOG_SNIFF = OFFLINE
DOG_PULSE = FRESH
=> FETCHER ready, local probe conflicts and should be refreshed
```

Fresh protocol heartbeat wins for FETCHER readiness because a functioning FETCHER necessarily reached the shared control plane even if one local probe method failed.

## Missing evidence

No current observation is not automatically OFFLINE.

If both pulse and sniff evidence are stale/unknown:

```text
host = UNKNOWN
fetcher = UNKNOWN
```

This distinction prevents absence from becoming a fake negative fact.

## LEASH_CLEAR / LEASH_TANGLED

The LEASH object is target-local infrastructure health.

```text
LEASH_CLEAR
    |
    | target TB4 infrastructure invariant fails
    v
LEASH_TANGLED
    |
    | invariant independently revalidated
    v
LEASH_CLEAR
```

Possible TANGLED examples:

- installed FETCHER service is broken;
- target-side Drive authorization unavailable;
- bootstrap configuration invalid;
- incompatible target protocol version;
- local permissions prevent required FETCHER operation.

Not enough by themselves:

- target temporarily offline;
- WOL timeout;
- one job FAILED/PARTIAL/GONE.

A tangled leash affects one player. It does not become `DOG_SHIT_BLOCKING` unless a separate global control-plane invariant also fails.
