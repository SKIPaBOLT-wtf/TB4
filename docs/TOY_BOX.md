# TOY_BOX Artifact Protocol

`TOY_BOX` carries scripts and large result payloads without turning FETCH_BALL into a giant command string.

## Identity model

A FETCH_BALL artifact reference is the **stable Drive object ID of an artifact descriptor**:

```text
FETCH_BALL
  payload_artifact_id
          |
          v
TOY_BOX descriptor object  <--- exact Drive ID, no folder scan
          |
          +-- content_object_id
          |
          v
TOY_BOX content object     <--- exact Drive ID
```

The descriptor ID is the protocol `artifact_id`. Runtime code must reject a descriptor whose body claims a different `artifact_id` from the exact object ID that was read.

## Publish sequence

A request artifact becomes usable only in this order:

```text
create content object
        |
        v
write complete content
        |
        v
remote readback
        |
        +-- verify exact byte size
        +-- verify SHA-256
        |
        v
create descriptor LAST
        |
        v
remote read descriptor
        |
        +-- schema valid
        +-- artifact_id == descriptor object ID
        +-- complete == true
        +-- content ID/size/hash match
        |
        v
FETCH_BALL may reference descriptor
        |
        v
FETCH_BALL_LOADING body verified
        |
        v
FETCH_BALL_TOSS
```

A partially uploaded content object has no valid descriptor and therefore cannot be a publishable FETCH_BALL artifact.

## Artifact kinds

- `REQUEST_SCRIPT` — executable script payload transferred as content rather than a giant remote command line.
- `REQUEST_DATA` — non-executable request data consumed by a job.
- `RESULT_TEXT` — large textual output.
- `RESULT_BINARY` — binary output.
- `RESULT_DATA` — structured or application data.

## Local execution safety

Remote metadata never supplies a local path.

FETCHER derives a temporary filename itself:

```text
controlled temp directory
     +
artifact_id-derived local token
     +
safe_suffix from fixed whitelist
```

For example, a verified PowerShell request may become an implementation-controlled temporary name ending in `.ps1`. The remote descriptor cannot provide `../`, an absolute path, a drive letter, a shell command, or arbitrary arguments.

`interpreter_hint` is a small enum. It is not executed as a shell fragment.

## Integrity

Before content is consumed:

1. fetch by exact `content_object_id`;
2. enforce configured size ceiling;
3. compare exact byte count to `size_bytes`;
4. compute SHA-256;
5. compare to descriptor `sha256`;
6. reject on any mismatch.

For executable artifacts this verification happens before creating or executing the local temporary script.

## Expiry and retention

`created_at` and `expires_at` use UTC Unix epoch seconds.

An expired request artifact must not start new execution.

Retention is owned by the later BONEYARD/TOY_BOX cleanup helper. Cleanup must preserve any artifact still referenced by live control state or otherwise protected by the canonical retention rules.

## Result artifacts

Small results remain inline according to `inline_result_max_bytes`. Larger results are stored in TOY_BOX and FETCH_BALL returns descriptor IDs in `result_artifact_ids`.

Result descriptors use the same integrity rules as request descriptors.

## Security boundary

TOY_BOX is data transport, not a secret store. Artifact support does not authorize placing credentials, private keys, tokens, or other secrets in the public repository or persistent control tree.

The artifact descriptor schema intentionally forbids path, filename, command, and argument fields.
