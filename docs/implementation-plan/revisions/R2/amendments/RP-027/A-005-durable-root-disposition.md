# RP-027 amendment A-005 — durable root dispatch disposition

Engineering extension of A-004 within ordinary authorized public implementation;
not live migration permission or acceptance evidence. Only unreleased schemas
and source are changed. The existing ordering document/objects, protected original
profile, operation identity/history, source pin and frame budgets remain intact.

The per-file protected pending record now distinguishes PREPARED, INVOKING and
REVOKED. PREPARED is saved before shared
effect start. INVOKING is saved with exact native readback while holding the same
actual native lock before the single SDK invocation. Its meaning is a possible
send, not proof that the server received or completed it. That lock spans final
owner proof and SDK call. Missing legacy disposition is UNKNOWN, never unsent.

An explicitly authorized prepared revocation requires fresh current owner/action/
clock/configuration/profile/source proof, BEFORE metadata and an exact exclusive
native current revision. It preserves REVOKED before releasing the lock. Any old
live invocation still using the prior revision/payload then fails its final check
before SDK send. Invoking or unresolved native pending state is never revoked by
guessing. Prepared-versus-revoked with AFTER metadata is contradictory and remains
CONFLICT; it cannot erase shared UNKNOWN.

A fresh typed RootRevocation is derived from actual protected current REVOKED and
exact previous PREPARED images, native binding/transition/operation/revision and
actual BEFORE metadata. Saved booleans, forged fields, changed native images,
another controller or copied profile do not constitute that proof. Explicit
same-frame native recovery remains inspect-only; a recovered possible-send marker
does not grant resend. The internal locked private-frame save reuses the existing
revision/binding/digest/exclusive stage/flush/promote/readback checks and cannot
open a port or grant authorization.

This unit does **not** clear shared UNKNOWN, retry the root operation, complete
inherited settlement or activate routing. Qualified same-authority effect
tombstones/known safe continuation and exact cloud after-witness settlement remain
separate subsequent work. Role takeover remains independent first strict-CAS stale
acquisition without old-machine/sink ACK. Folder rename, remote root/candidate
rebind, descriptor/configuration/lease/rollback and full C1-C4/native/platform/
packaged common gates remain required.
