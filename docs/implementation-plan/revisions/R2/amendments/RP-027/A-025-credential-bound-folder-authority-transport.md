# RP-027 amendment A-025 - Credential-bound existing-Folder authority transport

Date: 2026-10-05. Applies to RP-027.C2/C3; ordinary public implementation only.

## Qualified prerequisites and held composition

A023 actual Windows404/default3153 and both required Linux670 passed (327).
A024 actual Windows443/all39 new native/portable/default3192 and both required
Linux709 passed (332). This dependent source uses those qualified native held-file,
closed SSH-policy and explicit authority-purpose primitives. Immutable old
platform inspections321/330 still qualify only their respective source; they
remain tracked and must receive terminal reconciliation. No later source inherits
their package acceptance.

## Closed normal transport

FolderAuthorityRunner and CredentialAuthorityProcess are exact trusted types
bound to one actual platform native store/resolver/installation/endpoint and
FolderBinding. The qualified ProbeEndpoint is reused only for its protected
connection facts; it does not grant an authority purpose. No endpoint is read
from shared data or reconstructed durably here.

Before credential/native IO, the process validates only READ or CAS, exact
binding/nonce/fields and canonical bounded CAS body/revision. Only the fixed
tb4-folder-v1 command is sent through the qualified SSH policy. Configuration,
agent/default identities/certificates, alternate authentication/proxy/control
commands and arbitrary caller commands remain excluded. Existing normal helper
and read-only helper/proof/first-run APIs are unchanged.

Only FOLDER_AUTHORITY may invoke this fixed callback. Existing FOLDER_PROBE or
FETCHER-only images deny it. Each call borrows the still-held native selected key
and pinned known-host file, repeating current identity/permissions/version/
scope/trust/expiry/revocation and immutable composition checks. Linux uses the
sealed parent process descriptors; Windows uses canonical paths with read-only
native sharing. Neither key material nor a copied key file is exposed.

One private thread-owned slot permits one callback and correlated reply. The
slot lock is never held over resolver/native/process IO. Parallel/replayed/lost/
unrelated replies cannot replace or retain it. Closed READ snapshot and CAS
results are validated before private reply assignment; UseResult/LocalStore
still carry only Outcome. CAS ACCEPTED remains the existing result requiring
caller readback. Unknown or lost-after-commit replies require inspection and
never cause automatic retry or imply rollback.

## Scope and qualification

This is authenticated normal transport construction only. It does not supply
durable endpoint/profile metadata, bind RemoteFolderCommissioning to authority,
extend native runtime port allowlists, provision storage, authorize a workload
effect, promote configuration, migrate a deployment or activate the GUI/runtime.
Existing leadership/effect/operation/maintenance gates still govern future use.

Pure protocol tests cover fixed-command policy and malformed/foreign/ambiguous
requests/replies. Actual native Windows/Linux fixtures test borrowed-file closure,
private registry/history restart, lost credentials and pins, prior capability,
occupied slots, scope refusal and ambiguous after-CAS reply inspection without
resend. These callbacks use synthetic wire replies, not authenticated SSH.

Separate required actual Linux tests use fresh generated keys and the unchanged
fixed normal loopback helper for native registry restart, authenticated READ/CAS,
one conditional winner, stale/forced first-CAS takeover without former-owner ACK,
preserved UNKNOWN work, late credential/trust loss, lost-after-commit inspection
and unchanged original exchange files. Windows-to-Linux network authentication
is not claimed by Linux SSH plus Windows native fixtures.

Static inspection runs no tests. Separate published targeted/default collection,
required Linux and complete current platform/package qualification follow.
No RP-027 check is accepted by this source; durable endpoint/first-run/runtime/
GUI and all C1-C4 final-source common qualification remain held. Default
activation and schema/protocol/instruction hashes are unchanged.

