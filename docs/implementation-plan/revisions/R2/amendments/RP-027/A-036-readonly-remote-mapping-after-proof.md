# RP-027 amendment A-036 - Read-only remote mapping AFTER proof

Status: source foundation; no C1-C4 acceptance or installed protocol migration.

The gap review in A001 event0511 establishes that ordinary remote physical VERIFY
proves seals and current authority but cannot qualify the protected terminal
mapping used by server-local RetainedC4. This independent unit uses the already
qualified physical probe/native immutable mapping and fixed credential channel.
Current request38 and A034/A035 remain under qualification; no consumer relies
on their unaccepted results in this source unit.

## Closed opt-in observation

FOLDER_MAPPING_AFTER_PROBE_V1 uses the same fixed tb4-folder-probe-v1 command.
The request has the existing five header fields and operation VERIFY_AFTER,
blueprint, authority seal and mapping_sha256. Its nine flat fields contain no
path, executable or credential. The response has the five header fields plus
result, revision, body and mapping_sha256, also nine. Existing flat limits,
ordinary VERIFY and normal READ/CAS remain unchanged. Only the trusted closed
probe validator and fixed helper dispatch recognize this new mode.

The server obtains its mapping location solely from protected helper setup.
Its exact immutable native mapping must match the requested digest, transition,
authority/spec/handle and terminal shared folder_plan. The original mapping
anchor/parent and pinned root/database/journal identities must resolve uniquely
to the configured target. Existing physical verification checks every allocated
seal under its DB lock. After that observation the server rereads the full
mapping, target resolution and exact authority revision/body. Missing, pending,
changed, BEFORE, UNKNOWN, contradictory or damaged facts return closed UNKNOWN
without partial body or private errors. No file/CAS/key selection/move occurs.

The exact client checks a fresh nonce, protected selection/transport pins, all
closed response fields, complete current marker, immutable expected plan and
terminal identity outcome. Its opaque origin-bound proof is an observation.
Construction/replay/proof grants no role, readiness, effect replay or activation.
Old-host or all-peer acknowledgements are not inputs.

## Gates retained

The existing RetainedC4 exact server-local mapped AFTER guard is unchanged.
This unit does not add a remote consumer, native ACTIVE adoption or complete
staged/runtime composition. Qualify the new portable/native/actual SSH tests and
current platforms before those dependent units. Keep all common/C1-C4 checks
held, all failed histories and the owner deployment/privacy boundaries.
