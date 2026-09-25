# IP-03 Amendment A-002 - Add Target LEASH Vocabulary

Date: 2026-09-25

## Change

Add one target-local infrastructure fault logical object with canonical filenames:

```text
LEASH_CLEAR
LEASH_TANGLED
```

The internal logical object key is `TARGET_LEASH`.

## Reason

IP-08 requires a persistent per-device infrastructure fault representation that is explicitly not the global `DOG_SHIT` register.

`LEASH_TANGLED` means one target's TB4 infrastructure needs attention. It does not mean the whole BALL_PARK is blocked.

## Compatibility impact

Pre-v1 only. No deployed migration is required.

## Scope boundary

Examples that may tangle a target leash:

- target FETCHER installation/service broken;
- target-side Drive authorization unavailable;
- bootstrap configuration invalid;
- incompatible target protocol version;
- local permission failure preventing FETCHER operation.

Examples that do not by themselves tangle the leash:

- host temporarily offline;
- Wake-on-LAN timeout;
- command FAILED/PARTIAL;
- one lost work result.
