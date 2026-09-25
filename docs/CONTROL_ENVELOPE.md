# TB4 Common Control Envelope

The canonical schema is:

`protocol/schemas/control-envelope.schema.json`

It defines fields shared by reusable request/control objects such as FETCH_BALL, WAKE_BONE, and STOP_BALL.

## Encoding

Control bodies use UTF-8 JSON.

Reasons:

- parsers exist everywhere;
- JSON Schema can validate the structure directly;
- whole-body replacement/readback is simpler than append/prepend mutation;
- other AI/tooling can consume it without relying on line positions;
- small control bodies remain cheap to read in full.

Writers may emit a consistent human-friendly property order, but **readers must never depend on JSON key order**.

## State is not stored in the body

The lifecycle state is the current Drive filename of the stable logical object.

For example:

```text
Drive file ID: 1AbCd...
filename: FETCH_BALL_CHEW
body: { ... job identity and evidence ... }
```

The body intentionally has no `state`, `lifecycle_state`, or `filename_state` property.

This prevents two competing state authorities.

## Common identity fields

### generation

A monotonically controlled reusable-channel generation.

The same stable Drive file ID may serve many jobs over its lifetime. Generation fencing stops an old process from writing into a later reuse.

### operation_id

The current logical operation identifier.

It is generic so the same envelope can support a job, wake request, or cancellation request without inventing multiple incompatible identity mechanisms.

Object-specific schemas may add target-operation references where necessary.

## Time fields

Protocol timestamps are integer Unix epoch seconds UTC:

- `given_at`
- `expires_at`
- `started_at`
- `finished_at`

The value `0` means “not set yet” for lifecycle fields whose event has not occurred.

Local waiting/duration code will use a monotonic clock; wall-clock epoch exists for cross-machine protocol evidence.

Cross-field time relationships are validated by protocol/helper logic because JSON Schema cannot reliably compare arbitrary sibling numeric values.

## run_limit_s

A bounded execution-duration request.

The envelope imposes a hard protocol ceiling of 86400 seconds. Public configuration will define a much smaller normal maximum for this deployment class.

A zero value means no run limit is applicable to this object type, not “run forever.”

## Integrity fields

`payload_sha256` and `result_sha256` are lowercase hexadecimal SHA-256 values or null.

They describe the relevant payload/result content defined by the object-specific schema. They are not a second lifecycle state mechanism.

## Artifact references

The common envelope allows a bounded list of compact artifact references.

The later TOY_BOX protocol defines exact artifact kinds and lifecycle. The envelope only guarantees that every reference contains:

- stable artifact ID;
- bounded kind string;
- byte size;
- SHA-256.

## Whole-body mutation

TB4 does not use append/prepend mutation for control bodies.

The intended helper flow is:

```text
confirm writer-owned state
        |
        v
construct complete new JSON body
        |
        v
replace complete body
        |
        v
remote readback
        |
        v
schema + expected-value/hash verification
        |
        v
publish next lifecycle state
```

This is more deterministic than trying to reason about partially appended lines across a synchronized remote store.
