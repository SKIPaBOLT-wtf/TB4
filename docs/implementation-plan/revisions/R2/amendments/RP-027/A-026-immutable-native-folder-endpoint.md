# RP-027 amendment A-026 — immutable native Folder endpoint selection

This adds private connection metadata for the accepted Folder credential transport.
It does not change a shared protocol, Setup payload/choices, candidate schema,
credential image, selected scope, remote helper, runtime allowlist or activation.

## Scheduling and authority

Metadata preparation is independent of immutable platform inspections 348/352.
Its prerequisites are the accepted native private/credential foundations and the
qualified A023/A024/current A025 transport. It never invokes a credential or RPC.
Ordinary source and fresh synthetic native tests are authorized; existing
deployment profiles, real endpoints, keys, network and workloads are untouched.

## Closed private record

An explicitly selected, distinct actual Windows/Linux PrivateSettings store owns
one version-1 NATIVE_FOLDER_ENDPOINT frame. Its opaque fe_ reference, installation,
root/domain, blueprint and exact authority-handle digests, selected cr_ handle,
trusted ProbeEndpoint fields and current native store binding are immutable.
Endpoint fields include host/user/port, executable, pinned known-host file/version
and timeout; they remain private. No key bytes, key path, passwords or newly
granted capability are copied. The frame uses bounded deterministic native JSON.

Prepare requires exact explicit owner authorization and a fresh actual protected
Setup with the selected Folder credential metadata. Lookup repeats installation,
native-store, blueprint/authority, selected handle/target/trust and saved revocation
checks. Alias, stale model, changed pins, extra fields, lost metadata protection,
foreign selection and later revision are refused. Live key/expiry/known-file checks
remain the qualified resolver's per-use responsibility: metadata is never READY
proof or an alternative credential source.

## Interruption and limits

A pending or completed same native frame exposes only closed status and its
opaque reference. Creation cannot repeat over pending/current data. Recovery,
with explicit authorization, checks the same sealed revision-1/previous-null frame,
fresh current profile and exact reference before promoting existing pending bytes.
It does not reconstruct metadata, reselect/enroll a key, send a remote operation,
change routing or reset UNKNOWN history. Contradictory current plus pending,
changed profile or foreign reference is retained and refused.

Protected endpoint attachment/selection in first-run and the combined authenticated
proof/authority port, current runtime/GUI composition, package/platform evidence
and all RP-027.C1–C4 acceptance remain later work. No former-owner/peer ACK barrier
or metadata readiness condition is added to first-CAS stale/forced role takeover.
