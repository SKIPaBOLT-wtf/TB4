# RP-027 amendment A-022 - Closed Folder probe credential purpose

Date: 2026-10-04. Ordinary public implementation authority only.
Applies to RP-027.C2 and the installation-local credential-use boundary.
This additive scope does not alter accepted historical FETCHER purposes or
authorize an authenticated connection, installed change or workload effect.

## Independent scheduling and prerequisite boundary

Request21 (intent291) qualifies A021 on immutable source119e518 while this source
unit proceeds independently. Its prerequisites are the accepted RP-006,
RP-020/021 and RP-022 fixed-use/native/private metadata contracts, also retained
in the fully qualified prior sourcebf5c34f. It does not call or change A020/A021,
their helper/proof/transport or pending package artifacts. The same request21
runs remain inspectable and must receive terminal reconciliation. Connecting a
new credential transport to A021/runtime waits for both relevant qualifications.

## Purpose and dispatch

Add FOLDER_PROBE for one commissioned read-only existing-Folder proof callback.
It grants no READ/CAS authority, creation, provisioning, arbitrary command,
caller payload, replay, routing, election or activation. The trusted fixed runner
owns the helper/endpoint/trust and maps this purpose only to folder_probe.
This foundation does not implement that authenticated transport or return a
proof payload through the credential contract.

ExistingKeyStore dispatches FETCHER_STATUS, FETCHER_START and FOLDER_PROBE
explicitly. Untyped/unknown purposes or a missing fixed method yield DENIED;
they cannot fall through to fetcher_start. Per-use installation/target/trust,
scope, expiry, revocation, native identity/permissions/version and held-key
rechecks remain. There is one callback and no implicit retry. A callback that
raises or returns a non-enumerated result remains UNKNOWN with inspection
required, retaining the previous closed public outcome/report.

## Protected compatibility and audience

Setup choices and credential images accept only unique declared Purpose values,
bounded by the size of that closed enum. Existing one/two-purpose images,
references, versions, expiry and tombstones retain their meanings and round trip;
a newly selected three-purpose image can also restart. Old binaries that cannot
interpret an explicit new purpose must refuse it; it is not permission to mix
instruction/protocol revisions during an operation or migrate a live profile.

FETCHER enrollment summaries still expose only FETCHER_STATUS/FETCHER_START.
Folder commissioning is not a FETCHER bootstrap capability. Handles, locators,
paths, native identities, key bytes and provider text remain protected. No secret
material is copied to PrivateSettings or public reports.

## Evidence and remaining work

Portable tests separately cover Folder desktop/headless use and preserve the
original two-purpose Linux regression parameterization. Exact/missing methods,
wrong/untyped/foreign scope, stale local availability, revoked/expired/version
changes, lost/raw callback outcomes and private metadata restart are exercised.
Actual Windows/Linux fixture tests verify borrowed-handle closure, original
external key preservation, private image round trip and refusal after key loss.

Required Linux includes these tests without skips. Full final-source platform,
privacy, rollback/common gates remain. Trusted authenticated Folder proof
transport, durable private endpoint construction and runtime/GUI composition are
later bounded units; default DenyActivation and all C1-C4 holds remain.
