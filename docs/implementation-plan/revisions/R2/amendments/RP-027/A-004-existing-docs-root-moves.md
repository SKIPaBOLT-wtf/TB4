# RP-027 amendment A-004: exact existing Docs root moves

Scope: an unreleased C3 source unit under A-001/A-002/A-003. It does not authorize
live relocation, reset, installation, credential/network changes or workload replay.
It does not accept C3 or replace the required folder/C4 qualification.

The native Docs controller starts from the actual freshly validated staged Setup,
explicit C1 resolution and current owner/capability/clock/native reservation. It
records an immutable plan for the same document/tab/domain/capacity and all existing
artifact IDs from the exact protected resolution image. Original profile and central
work records remain unchanged; old/new metadata/spec/seals and target access are
verified. The existing control document remains the sole ordering point.

Each live per-file move records a protected native pending operation and confirms
shared IDENTITY UNKNOWN before invoking the provider. The native operation stays
exclusive across the final current-state/owner/UNKNOWN checks and SDK invocation.
Only that newly prepared call issues one metadata/parents update, with no upload,
create, copy, delete or automatic mutation retry. The API is the official
[files.update](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/update)
metadata patch with addParents/removeParents, described in the official
[folder guide](https://developers.google.com/workspace/drive/api/guides/folder).
No Drive conditional-write guarantee is assumed; strict Docs CAS orders shared
intent and role, while unresolved moves fence routing separately.

An exact opaque per-transition/key property witness distinguishes the operation
from a historical root reuse. Optional closed `root_transition` in a protected
native Docs storage record selects that expected witness. NativeCommissioning,
CommissionedStorage and the bound desktop selection check it; legacy absence
continues to expect exactly the original four properties. The witness is expected
metadata, never a grant, secret or proof of cancellation. Ordinary binding freezes
and first-run checks stay in place. Folder records cannot carry this Docs witness.

Restart, lost reply and local recovery inspect the same object/plan only. Exact
unique after metadata proves application; before/conflict is not permission to
repeat. Local pending promotion requires explicit owner, exact schema/native
binding/current/previous proof and readback; no SDK call is resumed. A cut before
shared dispatch may conservatively remain inspect-required; deterministic proven
non-dispatch settlement is a separate subsequent qualification, not inferred here.

Role takeover remains first strict-CAS stale acquisition with no incumbent/sink
ACK. A superseded sender cannot start another move. Its already sent UNKNOWN
survives; exact applied metadata can be observed without falsely clearing shared
UNKNOWN under an obsolete owner. Inherited-operation settlement remains explicit
subsequent qualified work, while role availability does not wait for it.

Moves complete only as physical metadata facts. They do not publish a new active
configuration. Actual first-run deliberately refuses the new storage until the
separate same-authority remote commissioning/catalogue rebind and candidate review.
Full folder physical rename, final descriptor/configuration/epoch promotion,
stale-cache/lease refusal, safe rollback and all C1-C4/common/native/platform/frozen
checks remain required. The WAL is bounded at128KiB and129 fixed objects, under
the existing1MiB private frame and current layout budgets. The schema is pinned
only in UNRELEASED; installed profiles/SKILL/builds are unchanged.

## Scoped effect admission repair (DEF-061)

The first exact root suite proved that using ordinary effect START during
maintenance prevents the intended root operation. ROOT_START is a separately
closed WAL purpose: only IDENTITY, actual current native grant/reservation,
matching maintenance transition and covered local-clear barrier, one new UNKNOWN
entry, unchanged settings/barrier and strict owner CAS. Ordinary START and normal
RecordMutation/runtime admission remain maintenance-denied. No effect receipt
grants an SDK send independently of the root controller's fresh proof/lock.
The new purpose is pinned only in the unreleased schema. The target-access test
retains the actual closed AuthorityError SETUP_ROOT and no-send/profile checks.
