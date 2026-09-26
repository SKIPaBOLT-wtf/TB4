# IP-28 Evidence - Tree Audit, Repair, and DOG_POUND Quarantine

Date: 2026-09-26

## Verified

- TreeAuditor enumerates folders only in explicit audit/repair mode; normal control paths remain PARK_MAP/exact-ID based.
- Canonical objects are checked by stable ID for parent, kind, and allowed deterministic active name.
- A missing canonical ID may adopt exactly one valid existing candidate instead of creating a replacement.
- Valid adoption candidates are not misclassified as unknown or duplicate objects.
- True duplicates preserve the PARK_MAP-selected canonical object and move only noncanonical copies to DOG_POUND.
- Unknown children in audited control folders are quarantined rather than deleted.
- Quarantine preserves bounded provenance in deterministic QUARANTINE_<hash>.json notes.
- Wrong-parent canonical objects preserve their stable object ID and are restored to the expected parent.
- Safely reconstructable missing objects are created only when blueprint policy permits it and PARK_MAP is updated after verification.
- Invalid stateful names block recovery rather than guessing an initial state.
- PARK_MAP identity ambiguity and root mismatch fail closed.
- Initial CI exposed a candidate-adoption ordering bug; the auditor was corrected so unique valid recovery candidates are preserved instead of quarantined.
- GitHub Actions CI run `36240656683` completed successfully for commit `2120243063488364e4342a269de3423580f65398`.

## Result

IP-28 completion criteria are satisfied.
