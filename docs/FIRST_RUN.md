# R2 first-run workflow

R2 settings are separate from installed v1 role profiles. The state machine owns
one installation UUID and one setup nonce, persisted before any external action.
They are not copied from a computer name, shared domain or another installation.
Device enrollment and target-slot assignment remain RP-025, distinct from this
local installation identity.

The protected choices contain a role, exact RP-019 storage specification and
authority handle, explicit network scope (including an empty isolated scope),
opaque purpose/target-bound credential handles, RP-011 timing and an RP-005 local
descriptor. Only missing role/storage/scope choices are requested from the owner.
OS, architecture and actual privilege are detected. Launch mode comes from the
trusted entrypoint; a desktop process cannot claim an installed service from a
saved preference. Linux desktop unlock state is explicitly unqualified rather
than guessed from environment variables. No discovery/network changes occur.

States are INCOMPLETE, BLOCKED, CANCELLED and SETTINGS_READY. Cancellation and
choices persist; settings readiness is process-local and expires on restart or
another settings revision. Saved READY fields cannot enable work. A cancelled
workflow remains cancelled until a local resume or explicit choice update.

Prerequisite validation reads the exact selected root, authority/tab/domain,
commissioning marker and allocated artifacts through the RP-019 adapter. It
checks current access, identities and artifact seals without creation or a root
scan. Missing or replaced storage is blocked, never repaired automatically.
Credential handles are checked through the installation's actual RP-006 resolver
for each selected purpose; unavailable restart bindings remain unavailable.
This model does not reconstruct a missing key binding from the handle string.
Selection metadata and chosen opaque handles are persisted together through the
same expected-revision transaction. Restart constructs a fresh native resolver
from that just-read protected image; the native principal/session is checked
again while the originally selected key version, purpose, target trust, expiry
and revocations remain unchanged. Key bytes stay in the selected external store.
The image is not a public JSON import or a configuration report. A stopped
rollback cannot restore older credential metadata or erase a revocation.

The local descriptor must match this installation/domain and pass RP-005 local,
shared and LLM projection validation; private topology remains in the protected
payload. Projection validation is not publication or discovery (RP-023/024).
Instruction selection uses the exact runtime build and a fresh compatible
RELEASED RP-007 profile. An ongoing workflow keeps its pin and rechecks eligibility
instead of silently switching instruction revisions.

Activation repeats prerequisite validation. Its trusted runtime entry adapter
must independently check release/deployment authorization, enrollment and native
runtime context, and the runtime still enforces leadership/operation checks at
each boundary. Product setup entrypoints default to DenyActivation while R2 is
unreleased. A passing synthetic activation fixture is not live authority.

The bounded commissioning action method records UNKNOWN with durable readback
before calling a trusted action once. Both a successful return and a lost reply
require same-operation inspection; cancellation/restart cannot replay it. Root
binding is frozen after any external operation; UNKNOWN also freezes changed
choices. Rollback creates a new local revision while stopped and refuses to erase
identity, root binding or operation history. It never rolls back external effects
or recreates an unknown deployment.

## Local desktop entry

An explicit `--action setup` opens the R2 local setup flow. A fresh default GUI
without an installed v1 config enters the same flow; an existing config continues
to open the v1 role window. Nothing migrates that profile. `--setup-root` selects
an explicit private R2 location. Otherwise the application proposes a role-local
standard user location, creating no directory until the owner clicks Create/Open.
Windows requires an already-private parent; refusal never repairs existing ACLs.
Reopening first reconciles the same complete staged next-revision frame through
the qualified private-store recovery method. An interrupted first identity or
cancel/update therefore resumes through the ordinary UI. Partial/corrupt or
contradictory staging remains blocked and untouched; an existing empty directory
does not authorize minting a replacement identity.

The UI persists the requested root separately from its verified storage binding.
A folder selection and network scope are choices, not proof of access. Reopening
keeps those choices so they are not requested again. A trusted RP019 connection
context supplies the selected storage adapter. ConnectedDocsSelection resolves an
existing domain by bounded inspection of the owner-selected root, then pins exact
document/tab/domain/spec identities and uses exact reads on later checks.
BoundFolderSelection checks the installer-selected qualified Linux mount and its
existing domain. Neither creates a replacement root or changes network settings.
Preparing a new domain remains the separately authorized RP019 commissioning
helper's responsibility; this selection flow only adopts verified existing work.

The current standalone unreleased entry has no automatic provider login, target
enrollment, descriptor discovery or production release authority. It saves owner
choices and explicitly blocks missing connection context. Programmatic installer
or commissioning composition supplies already authorized adapters; it cannot
supply a public READY boolean. This is the RP022 workflow handoff, not a claim
that RP023/024/025 discovery, descriptor collection or enrollment has shipped.
The default entry always uses DenyActivation. No Start Role control bypasses it.

Checks run in a Qt worker while editing is disabled; close waits for that bounded
check. Cancel/resume persist through the same protected model. Local selected
paths may be shown only in the local setup UI; errors and status use fixed text.
There is no raw credential editor, protocol JSON form or private-data exporter.
Optional local key selection is shown only for already approved target entries.

Package acceptance imports these modules and opens the actual frozen first-run
location window for both roles. This smoke intentionally creates no settings and
starts no runtime. Separate native tests qualify actual protected files and
credential restoration on each supported OS; those tests are not inferred from
the GUI smoke result.
