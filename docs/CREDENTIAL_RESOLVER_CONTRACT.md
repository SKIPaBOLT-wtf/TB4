# Local credential-reference resolver contract (RP-006)

`tb4.credential_contract` defines a local-only enrollment/capability/fixed-use
interface. It contains no implementation that reads a real key, OS secret store,
OAuth file or SSH profile. Tests use a synthetic in-memory adapter. Native secure
storage/ACL handling is RP-020/021; fixed Windows/Linux helpers are RP-036/037.
This contract does not claim that either production integration exists.

## Binding and audience

Enrollment creates a random `cr_` plus 128-bit opaque local handle. No host,
username, account, address, path or target identity is encoded in it. The protected
binding separately records installation UUID, stable target UUID, pinned target
trust fingerprint, approved-store locator, exact permitted helper purposes,
expiry, generation and revocation. Handles and locators stay local; BALLPARK and
LLM capability reports never receive them. Binding repr omits protected fields.

The initial RP-006 purposes are FETCHER_STATUS and FETCHER_START. There is no arbitrary
command/payload argument. An authorized trusted local setup controller enrolls
the minimum needed purpose set. Owner authorization is control state established
outside the incoming LLM/device proposal; passing a boolean from remote JSON is
not a production authorization mechanism. The store adapter must match the local
installation. A copied incumbent binding or another installation's store fails.

## Local adapter obligations

The approved adapter alone accesses material. It validates allowed store/key-file
scope, ownership/ACL/private-mode requirements, store lock, expiry/revocation and
the target trust binding. A filesystem path existing is not permission proof.
Symlinks, unapproved stores, overly broad ACLs and unavailable permission evidence
must fail closed under the platform integration. The contract requires explicit
approved-store and permission-verification flags plus a local store generation.

Every invocation rechecks the binding, time and local inspection. The adapter's
`use_fixed` must recheck current permissions, lock/revocation and expected store
generation atomically with its own fixed-use operation; inspect-then-use alone is
insufficient. The adapter resolves material internally and returns only an enum.
Returning a raw provider object/string cannot become a successful public result.
Synthetic race tests demonstrate the required behavior, not native ACL proof.

Capability outcomes are READY, ABSENT, LOCKED, EXPIRED, REVOKED, MISMATCHED, DENIED
and STORE_UNAVAILABLE. Reports contain only configured/available booleans and the
fixed outcome. Invocation adds SUCCEEDED or UNKNOWN; it returns no secret, path,
handle, account, exception text, stdout/stderr or custom exception class name.
SUCCEEDED means the commissioned fixed helper completed, never that FETCHER is
ready; fresh independent runtime acceptance remains required.

There is one attempted fixed call per invocation and no automatic retry. Lost
acknowledgement or malformed adapter output means UNKNOWN and inspection_required.
The caller must retain durable operation identity and inspect the same effect
before another mutating call; this in-memory contract does not implement durable
deduplication or authorize replays. Those are separate execution/ledger gates.

## Rotation, revocation and rollback

An authorized local controller stages replacement material in an approved store.
Rotation creates and verifies a new local binding, then revokes the old handle;
unavailable/expired candidate rollback removes only that uncommitted binding and
keeps the prior binding intact. It does not delete or modify any key material.
Unrelated bindings remain available. Generation changes and per-use rechecks
prevent a previous capability observation from authorizing later changed state.

Binding revocation prevents subsequent TB4 use through that resolver. It is not
provider-side credential revocation and does not erase a key used by another
service. Exposed credentials still require separately authorized revocation and
rotation at their actual authority, plus private canonical documentation.

A standby resolver reports only its own local store/bindings. It cannot import
another installation's identity or advertise READY from an incumbent's summary.
Missing or mismatched capability is explicit. Re-enrollment requires separate
local authorization; there is no automatic fallback to another profile.

The legacy `OPENSSH_CONFIG` transport remains historical compatibility behavior,
not proof of this installation-scoped contract. No legacy binding is migrated,
copied or deployed by this change. Its raw internal transport/result objects are
not public diagnostic artifacts; later fixed adapters must adopt the new safe
result boundary. Rollback removes/revokes only newly introduced local metadata
and reports capability unavailable while keeping unrelated credentials untouched.

RP-027 [A-022](implementation-plan/revisions/R2/amendments/RP-027/A-022-closed-folder-probe-credential-purpose.md)
adds the explicit read-only FOLDER_PROBE fixed purpose. Only its commissioned
folder_probe callback may run; a missing method is DENIED and never maps to a
FETCHER command. Public results remain the same closed outcomes/booleans, with
no arbitrary payload or secret return. Protected images/choices accept unique
declared purposes up to the closed enum size, retaining old metadata meanings.
FETCHER summaries retain their original two purposes. This foundation does not
construct an authenticated Folder transport, expose a physical proof through
UseResult, migrate an installed binding or grant activation/runtime authority.
