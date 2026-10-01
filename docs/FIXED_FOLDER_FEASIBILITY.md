# Fixed-folder authority qualification probe (RP-018, not yet accepted)

The requested alternate folder capability cannot use independent synchronized
copies as one transaction authority. Google/native Docs remains the selected
mode; no current domain is switched or duplicated. Candidate implementation:
one server-local directory containing preprovisioned transaction files, accessed
only through one fixed per-call helper protocol by every role and authorized
LLM adapter. It requires no resident extra coordination daemon. Direct cloud
sync, NFS/SMB database-file access and missing same-exchange LLM access are not
silently supported by that candidate.

First qualify its fixed-object crash behavior. SQLite supplies transactional
locking and rollback on a local filesystem, subject to correct OS/storage flush
semantics. PERSIST keeps the rollback journal rather than deleting it on normal
commit; EXCLUSIVE locking is set before the first database access. Whether
reopening a killed writer also retains the same journal object is an acceptance
question for the actual probe, not an assumption in this document.

The small synthetic probe creates only a new caller-specified test directory.
It records file identities internally, starts two independent revision-CAS
clients, then interrupts only its own uncommitted writer after its update has
returned. It checks that database pages actually changed before that interruption,
reopens through the same candidate connection policy, and compares exact last
committed revision/content plus the fixed file names and identities. A missing
journal must be refused before SQLite can create a replacement. Public output
contains only synthetic outcomes, sizes and identity-equality booleans.

This is not a production adapter. No real SSH endpoint, network share, native
filesystem power failure, permissions model, installation, or LLM connector is
qualified by a local probe. If the fixed-object invariant passes, RP-018 must
still implement closed identity/capacity/permission gates, strict operation
readback and remote-helper conformance; otherwise retain the counterexample and
select a different authorized design. No extra control plane or native-Docs
fallback can hide a failed gate.

Primary design references: [SQLite atomic commit and filesystem assumptions](https://sqlite.org/atomiccommit.html),
[persistent journal mode](https://sqlite.org/pragma.html#pragma_journal_mode),
[SQLite network-filesystem caveats](https://sqlite.org/useovernet.html).
These sources explain the candidate; the attempt journal and observed test
evidence determine what was actually established on each platform.
