# RP-027 A-021 - Typed remote Folder first-run observation

Status: additive unreleased implementation under public development authority.
This source accepts no RP027 check and authorizes no installed/live change.

## Invariant and selected boundary

A020's fresh physical proof can satisfy the existing first-run storage check
through one exact typed read-only adapter. The trusted local caller supplies the
already selected FolderProbe. Construction pins its exact original spec, handle,
binding, fixed process and origin. Each CommissionedStorage verification matches
the current protected storage selection before IO and invokes the exact probe
implementation once. It validates the resulting origin and current ready document.

There is no client-side per-artifact RPC loop, saved success flag, alternate root,
generic verifier callback or additional runtime grant. The server's A020 proof
already checks every allocated physical seal under its single database lock.
An old nonce, missing/changed artifact or inaccessible helper prevents the new
first-run review with the existing closed STORAGE_UNAVAILABLE reason.

## Protected state and first-run integration

Actual Setup/Prerequisites review and restart consume the adapter through the
same CommissionedStorage wrapper. Each later review and activation attempt
repeats the physical proof. Existing setup identity, nonce, choices and operation
history remain. UNKNOWN work still blocks review before probing and never grants
replay. Default DenyActivation stays closed after a successful storage observation.

The adapter exposes only spec/root/mode and verification. It is deliberately not
added to runtime admission or mutating reconfiguration port allowlists in this
unit. A physically verified snapshot alone cannot construct their authority.

## Qualification and remaining dependencies

Portable tests cover exact selection, changed trusted pins, stale replies,
closed failure/no retry, actual Setup review and default denial. Actual protected
Windows/Linux fixtures verify restart/activation/UNKNOWN preservation. Linux
owned fixtures exercise the real helper subprocess and isolated generated-key
SSH with fresh physical failure after success, preserving remote payload/inodes
and logical revision. Required Linux jobs execute these cases without skips.

The trusted authenticated host/credential-purpose/fixed-command construction is
still a separate required unit, followed by runtime/GUI and complete RP027/common
acceptance. A generic fixed argv or synthetic reply is not live deployment evidence.
No provider, actual LAN/router, installed profile/SKILL or credential is changed.
Rollback of this uninstalled source retains the existing native Docs/local Folder
verification and all prior source, work and failed qualification evidence.
