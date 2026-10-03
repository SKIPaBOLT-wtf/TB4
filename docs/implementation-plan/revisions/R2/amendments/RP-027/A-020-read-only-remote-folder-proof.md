# RP-027 A-020 - Read-only remote Folder commissioning proof

Status: additive unreleased implementation scope under existing public development
authority. No installed helper, credential, profile or live migration is authorized.
Acceptance remains in the manifest; this source does not accept C1-C4.

## Invariant

A remote READ of the authority body does not prove that its allocated physical
files still exist with the commissioned identity. First-run integration needs a
fresh observation of the current ready marker, blueprint, authority identity and
every allocated artifact seal. This proof does not depend on the former WATCHDOG
or any peer acknowledgement. Election remains the first successful stale-record
CAS; inherited UNKNOWN work never grants replay.

## Closed boundary

The existing helper stays READ/CAS by default. A separately commissioned fixed
command may explicitly select `--commissioning-probe`, which accepts only a
`FOLDER_COMMISSIONING_PROBE_V1` VERIFY request. Its exact fields are the existing
version/root/domain/nonce envelope, operation, expected blueprint hash and expected
authority seal. It accepts no client path, command, credential, allocation or body.
Ordinary READ/CAS and probe envelopes cannot be substituted for one another.

The server resolves its protected configuration and optional mapping before any
probe lock. It verifies the fixed authority and ready original commissioning
marker, then holds the existing database lock while reading the snapshot and
checking all physical allocated object identities, permissions and seals. It does
not resolve a mapping or open SQLite recursively under that lock. Current config
identity and root checks finish before a correlated VERIFIED response is returned.
There is no logical shared mutation, create, rename, reset, scan or retry.

The response adds only result, revision, canonical body, blueprint and authority
seal to the envelope. The exact typed fixed-process client checks all fields,
expected bindings, fresh nonce, ready marker and canonical body. Failures return
only UNKNOWN or a sanitized PROBE_UNAVAILABLE. Existing wire, process and helper
alarm bounds remain; a saved reply cannot satisfy a later nonce.

The trusted caller supplies authenticated host trust, credential purpose and the
fixed helper command from protected commissioning. This source does not implement
that resolver composition or make a generic argv safe. The proof is an observation,
not a current-role grant, durable READY flag or permission to adopt/activate work.

## Qualification and follow-on

Portable tests exercise closed request/reply fields, stale or foreign replies,
binding/access restrictions and the unchanged default handler. Actual Linux tests
check used payload/inode/revision preservation, missing/replaced/aliased or
mispermissioned artifacts, wrong seals/markers, incomplete commissioning and lock
ordering. Isolated generated-key loopback SSH exercises the actual opt-in forced
command and repeated fresh physical access checks. Required Linux CI installs its
own ephemeral SSH prerequisites; skipped required cases are not qualification.

Subsequent typed remote first-run, protected credential/transport composition,
runtime/GUI integration and final-source platform/common acceptance remain required.
Synthetic portable replies do not establish Linux physical or Windows-to-Linux
deployment evidence. Default activation remains closed. Rollback of this uninstalled
source retains the original READ/CAS behavior and all existing operation history.
