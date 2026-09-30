# R2 planning-snapshot validation

Date: 2026-09-30. Item PLAN-R2 / A001. This verifies planning artifacts only,
not implementation of RP-001, any runtime capability, a build or a live deployment.

## Observed result

The local planning-snapshot validator completed with exit code 0:

- 64 unique ordered RP step IDs and 256 unique C1..C4 check IDs.
- 22 requirement groups, each mapped to steps; forward/reverse mappings agree.
- 351 dependency edges; every dependency exists and precedes its consumer.
- No cycles; RP-064 transitively requires all 63 earlier steps.
- All 64 statuses PLANNED; no completed checks, fabricated evidence or active attempts.
- 64 checklist links point to the corresponding definitions.
- YAML/JSON files parse; new Markdown relative links resolve. The unchanged
  baseline link was checked against the connector-read existing file, not a local stub.
- Each step has explicit deliverable/input/check/acceptance/rollback boundaries.
- Two negative fixtures (a dependency cycle and an unknown dependency) were rejected.

The validator checked 75 Markdown files before this report was added. Navigation
and the final checkpoint were also parsed/reviewed before publication. Automatic
structural validation does not prove that every future design decision is solved.

## Exact publication correspondence

The validated R2 directory, before adding this report, has Git tree:
`a031a9f594acfc9895136469e4c857a2b35d085a`.
GitHub independently returned the same tree at source checkpoint
`56110d29b5c808bf74903f1484b603d7cbfec911`.
It covers all 64 step definitions, manifest, checklist, requirements, addendum,
privacy/portability matrix, defect index and R2 README.

Additional local/remote matches:

- Work instruction blob: `9af06edac1d78bae8a7be6b55ef05f2ad9199854`.
- Record-template directory tree: `d2930397beca4fe1e80c96f2342631c664f1725f`.
- Manifest blob: `900181954e976b017a649e52e5b692c07cceaa2c`.
- Requirement mapping blob: `57bc3e7caff7db1d9d370cf07c71e9c9b6369382`.
- Step-definition subtree: `bf03da0a56eaedd585a9010ab445db118909d6d5`.

## Procedure and review boundaries

A local Python/PyYAML check parsed the manifest, required sequential stable IDs,
counted exact checkbox identifiers, compared both requirement mappings, traversed
the dependency graph with cycle detection, checked the final ancestor closure,
verified initial acceptance fields, parsed YAML/JSON, resolved Markdown links,
and injected the two invalid graph fixtures. Git object hashes were calculated
from actual UTF-8 file bytes using the standard blob/tree representation and
compared with GitHub connector reads. No source checkout or runtime execution
was required; source was read and updates were published through the connector.

During assembly, validation first found an absent local RESUME mirror; after
adding navigation it found that the unchanged baseline was not copied locally.
The cursor was assembled, and the baseline was explicitly treated as a previously
connector-verified existing file. No missing link was hidden by a dummy document.
An earlier local draft-script quoting error was corrected before generating its
output. These were planning-assembly issues, not TB4 runtime test failures.

Content review checked role separation, common ingress, exact required intervals,
fixed capacity, incumbent/fallback fencing, failure/ACK semantics, first-run
BALLPARK creation/evolution, reconfiguration versus reset, local credential
bindings, pointer-only installed SKILL and version-compatible repository guidance.
Unresolved mechanisms remain explicit decision gates, not silently assumed support.

The existing IP manifest/evidence and runtime/protocol/configuration/packaging/
operational SKILL paths must remain unchanged in the final comparison. Development
navigation is intentionally updated to CURRENT/R2/RESUME. No private deployment
facts or secret values were read or added to these new planning artifacts.

## Deliberately not claimed

No RP step is VERIFIED by this report. No test suite for TB4 runtime was run,
no installer was built/changed, no SKILL was installed, and no command or recovery
operation was sent to a managed host/Drive exchange. DEF-001 and DEF-002 remain
open with unknown proven origin. Ledger automation itself is planned in RP-001
through RP-003; this planning checkpoint was prepared with manual connector
transactions and local structural checks.
