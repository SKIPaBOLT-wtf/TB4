# Public evidence and protected deployment data (RP-004)

This field-level policy applies to development progress, diagnostics, exports and
later BALLPARK commissioning. `tb4.privacy` provides closed, testable report and
private-projection contracts. Existing generic text redaction and repository
scanning are supplementary detection, not proof that arbitrary data is public.

| Data | Classification | Allowed destination |
| --- | --- | --- |
| Generic schema/version, fixed role/state/stage/outcome codes | Public candidate | Closed public report, after review |
| Public source SHA, RP/check/attempt IDs, reviewed synthetic observations | Public candidate | Development ledger with provenance/review |
| Real addresses, routes, subnets, ports, hostnames, interfaces, domain/device IDs | Protected | Authorized deployment configuration |
| Drive root/object IDs, local paths, usernames, raw provider IDs, exact activity times | Protected | Minimum necessary private operational store |
| Credential handles, account/store/key locations and binding metadata | Protected local | Installation-local resolver configuration |
| Curated nonsecret aliases and commissioned capability booleans | Protected shared | Explicit PRIVATE_LLM projection only |
| Passwords, tokens, private keys and credential values | Local secret | Approved local secret store; never a descriptor, LLM or report |
| Raw config, environment, payload, stdout/stderr, URLs and provider bodies | Protected, potentially secret | Private result/recovery workflow only |
| Screenshots, binary artifacts and arbitrary export names | Unreviewed protected | Private review; no automatic public export |
| Unknown field or unconstrained string | Protected by default | Never infer public status from spelling or encoding |

Classification alone does not authorize collection or publication. A string that
looks like an uppercase error code can still contain a token. A hashed address,
path or identifier remains private data; hashing/encoding is not anonymization.
Secrets must never be placed in a curated alias. Setup must verify nonsecret
alias intent before sharing it; this contract cannot infer the meaning of text.

## Closed publication contracts

Public diagnostic v2 carries only fixed role/process/stage/outcome/protocol/error
codes and a freshness category. It omits timestamps, paths, object identities,
credential handles and arbitrary strings. Unknown values are omitted or rejected.
`public_artifact` validates the entire closed report and derives a fixed filename
from the approved role; it never copies an incoming filename. It rejects binary
screenshots, raw text, logs, configuration and the private projection. It performs
no upload. Pixels and arbitrary command output are not automatically sanitized.

Private telemetry v1 retains bounded timestamps needed for local observation.
Worker transport, local event logging and diagnostic export enforce known values;
unknown uppercase strings and custom exception class names are not public codes.
The event-log boundary revalidates rather than trusting an arbitrary dictionary.
New legitimate codes require reviewed source additions; unknown provider text is
reported as a fixed generic category. This intentionally favors non-disclosure
over preserving an unrecognized message. Stored result bytes remain private and
are not silently rewritten by this diagnostic contract.

The separate PRIVATE_LLM projection includes only curated aliases, fixed roles
and three declared capability booleans. Missing capabilities default false. It
does not carry addresses, paths, resolver handles, credentials or raw source
configuration. RP-005 owns full topology/revision validation; this is its privacy
boundary, not evidence that commissioning is implemented. Private projection
validation is never a grant to publish it to GitHub.

## Pre-upload review and exposure containment

1. Confirm the destination, authorized audience, exact file set and purpose.
2. Prefer minimal closed reports or fresh synthetic reproductions. Review values,
   filenames, metadata, nested fields, archives, links, encodings and image pixels.
3. Check the public scanner and inspect the final staged diff/artifact. Never add
   raw provider/config/console dumps to make a failed run easier to reproduce.
4. Publish only the reviewed artifact and read it back. Automated safe-report
   validation does not replace human review of public prose and binary media.
5. If exposure is suspected, stop further publication and retain a restricted
   record of affected object/commit/run identities without copying the secret.
   Restrict/remove exposed artifacts through authorized controls; do not assume
   deletion, GitHub masking or rewritten history revokes a credential.
6. Revoke/rotate affected credentials at their authority, review access/activity,
   update protected canonical bindings, and verify the replacement through local
   use. These are separate authorized incident actions, not automatic privileges
   granted by this document. Publish only the safe incident outcome.

Rolling back a sanitizer keeps the publication block and review requirement in
place. Never re-export an old unreviewed log. Existing diagnostic v1 consumers
must recognize that public exports are now v2; local worker snapshots stay v1.
