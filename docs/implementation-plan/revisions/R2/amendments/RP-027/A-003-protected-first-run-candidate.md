# RP-027 amendment A-003: protected first-run candidate

Scope: unreleased RP-027.C2 implementation. This supplements A-001/A-002 without
changing accepted RP identities, election timing or deployment permission.

An owner-approved candidate begins only after the current WATCHDOG has a fresh
explicit C1 resolution. The complete original protected Setup payload, including
all operation outcomes and derived packages, is retained once in an immutable
first-revision native archive. Its original revision, payload digest, installation,
transition and every new native directory binding are checked. Native frame
protection, locking and exact readback remain mandatory.

The candidate is a separate actual Setup with the same installation and nonce.
It preserves operation history, credential metadata and network-table selection.
Old discovery, descriptor publication and enrollment packages remain in the
archive; they are absent from the candidate and cannot be reused as new routing
evidence. Existing Setup binding freezes are unchanged. The staged core permits
owner proposals for network scopes, descriptor, timing and credential selection.
This first unit keeps role, root, backend, domain, capacity and fixed authority
unchanged; C3 relocation and C4 cache/publication/promotion require later units.

Validation uses the same actual Prerequisites and CommissionedStorage as first
run, including current environment, selected installation/purpose/trust-bound
credential availability, actual fixed-object access/readback, descriptor/timing
and instruction boundary. An arbitrary READY checker, saved SETTINGS_READY or
deserialized certificate is insufficient. Every final validation repeats these
probes and C1 resolution. A trusted desktop controller retains DenyActivation.
Original settings and authority/work records are not written by this controller.

Durable closed candidate metadata precedes archive/profile staging. A local cut
preserves its exact native pending frame. Explicit recovery validates that frame's
schema, native binding, previous/current revision, original evidence and history
before promoting the same bytes. Missing stages can be completed only through
explicit owner-approved resume after fresh proof; no external action is replayed.
Archive rewrite, directory alias/copy, changed original profile or unresolved work
refuses further use. Saved readiness becomes false after restart/recovery.

The candidate payload is bounded at384KiB to retain its previous value within the
existing1MiB private frame, and metadata at64KiB. Original archive is immutable
and subject to the existing native frame budget; oversized input fails closed
while original settings remain intact. No allocation budget or JSON generation
limit is enlarged; generations retain the exact signed64-bit maximum.

The new reconfiguration-candidate-v1 schema is pinned only in UNRELEASED; no
installed profile/build/SKILL or live configuration is modified. Source alone
does not accept C2 or close mandatory C1-C4/common/platform/packaged rechecks.
