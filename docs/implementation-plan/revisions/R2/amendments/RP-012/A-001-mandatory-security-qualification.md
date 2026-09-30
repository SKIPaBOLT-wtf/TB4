# RP-012 A-001 — mandatory downstream security qualification

RP-012.C4 requires unresolved security assumptions to be acceptance blockers.
`docs/SECURITY_FAILURE_CONTRACT.md` and the closed
`protocol/drafts/r2-security-matrix.json` inventory name those blockers and their
owning steps. All real capability gates remain NOT_QUALIFIED by this design.

RP-059, RP-060, RP-061 and RP-064 must review the selected mode against that
inventory and refuse acceptance/release while required actual evidence or scoped
live authorization is missing. The inventory includes native CAS, actual private
principal ACL and cooperative role enforcement; protected OS credentials and
process identity; durable unknown-work/output completeness; bounded parser,
media, rate and log behavior; instruction/result separation; required native
packages, same/separate-host topology, session, launcher/no-launcher, wake and
network capabilities. Each inventory gate names its implementing step owners.

Synthetic predicate booleans or a caller-supplied set of gate names are never
proof of authentication, runtime capability, acceptance or owner authorization.
Unsupported modes must be explicit; an unqualified essential promised product
requirement cannot silently become optional. This amendment adds traceable
downstream obligations, changes no earlier accepted check or installed v1
behavior, and grants no live deployment authority.

The one-document trust model remains private authorized cooperative editors;
there is no per-field provider ACL or hostile-code sandbox. Owner-approved
available WATCHDOG takeover remains immediate after successful qualified CAS,
without incumbent or all-sink ACK. Unknown prior effects remain individually
reserved and reconciled, not a global role-transfer barrier.
