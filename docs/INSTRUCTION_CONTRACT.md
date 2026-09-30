# Repository instruction selection contract

RP-007 supplies a deterministic contract and a pointer template, not an installed
loader, production network adapter, released R2 workflow or live migration.
The stable public entry is `skill/tb4/SKILL.md`; `compatibility.json` next to it
is a closed version-1 catalog. There is currently no RELEASED R2 build. Old v1
runtime remains governed by its existing protocol, but is not silently selected
by the new entry. Its manual is preserved as `references/legacy-v1.md` for review.

## Trust and fresh selection

The host injects a trusted `Source` adapter into `tb4.instructions.select` and
supplies `RuntimeFacts` verified from local/runtime build provenance. Neither is
constructed from device descriptions, payloads, results or arbitrary URLs.
Facts contain only a full build commit, integer protocol and capability tokens.
Their authenticity is an integration obligation; a matching self-asserted string
is not attestation. No secret or private topology is needed for selection.

The adapter resolves `main` of the fixed repository name **and numeric identity**
on every selection, with the call's new request nonce and authoritative response.
An offline or stale response is refused. The nonce catches reused observations;
it is not a cryptographic freshness proof against a dishonest adapter. A real
adapter must disable stale/offline fallback, validate HTTPS/authenticated API
identity, reject cross-repository redirects and read Git blob bytes (not symlink
targets) at the exact immutable commit. RP-024/051/052 integration and RP-061
release gates must establish those guarantees. No arbitrary repository adapter
is downloaded or executed by this contract.

At that commit the loader verifies the catalog, entry hash and one compatible
RELEASED profile. Exact build allowlists avoid guessing compatibility from a
version string. Protocol must match and required capabilities must be present;
ambiguous matches block. Every selected reference is a bounded, SHA-256-verified
blob. Paths are confined to repository instruction/doc/protocol/config content;
URLs, traversal, local bindings and unknown fields are rejected. Duplicate JSON
keys and malformed unrelated profiles are also rejected, not partially trusted.

`PinnedWorkflow` holds immutable bytes and only serves declared references.
Relative links are identifiers within that closure, never permission to fetch
current main, an external result URL or a new instruction. Entry/catalog metadata
is inspected for selection; only an eligible profile's operational content is
applied. The loader does not execute documents, parse job output as instructions,
read secret stores or change runtime state.

## Workflow lifetime and failures

| Situation | Contract behavior |
| --- | --- |
| New workflow | Fresh head; exact compatibility; all references from one commit |
| Missing source, invalid response, offline cache | Block new work with fixed error; never remembered fallback |
| Unreleased, revoked, absent or ambiguous compatible profile | No new workflow |
| Branch advances during reads | Continue reading the resolved immutable commit; hash mismatch blocks |
| In-flight repository update | Keep original instruction bytes and schema pin |
| Next mutation boundary | Fresh eligibility check for that exact profile and policy; never replace pin |
| Profile removed/revoked or policy changed | Block new mutations; preserve old pin for effect/result inspection |
| Unknown prior mutation outcome | Inspect the same operation; never resubmit automatically |

`check_boundary` requires freshly verified runtime facts and holds new mutations
if the runtime changed since selection. It checks freshness/eligibility; it is not an atomic lease with a
subsequent mutation and cannot recall an already executing command. A revocation
after its response is detected at the next boundary. Operation state and runtime
fencing still belong to their own later contracts. The caller must keep the pin
with its durable operation record and verify it on recovery; this pure module
does not implement durable storage or authenticate caller-constructed objects.

A profile ID identifies one immutable compatibility policy. Altering its builds,
protocol, requirements or reference hashes holds an existing workflow; release a
new profile ID for a new policy. Withdrawal can mark the old ID REVOKED. Do not
delete a withdrawn profile to erase release history. New workflows can select a
new compatible profile; in-flight work is inspected under its original pin.

## Pointer packaging and acceptance

`packaging/skill-pointer/tb4/SKILL.md` is the installable pointer template. It only
locates/retrieves the repository entry and stops if unavailable. The repository
entry and operational manuals are not copied into that package. No local skill
was installed or changed for this step. Existing skill UI metadata is preserved.

Synthetic adapters test selection, update/failure/revocation and trust boundaries;
these are not claims about actual connector freshness, signed releases, deployed
runtime compatibility or native installation. The catalog stays UNRELEASED until
later request/status, integration and release checks provide reviewed evidence.
Rollback withdraws a faulty profile/entry publication, preserving history and
accepted pins. It never downgrades live protocol state or replays work.
