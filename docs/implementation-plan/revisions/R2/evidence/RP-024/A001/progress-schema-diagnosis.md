# RP-024 progress schema diagnosis

At checkpoint70ce16b0c2bdce550f18770491c082c5eb4db9dd, closed JSON schemas report
only `docs/development/RESUME.yaml` root `additionalProperties`. The task passed
`known_defects` at RP0240004/df1af54e5a2af3808f9dfde06e343d7bf1e3cf84. The canonical
CURSOR schema uses `known_open_defects`; cursorFn merges and persists input keys,
so subsequent checkpoints retained the typo. EVENT/MANIFEST/DEFECT shapes passed.

Initial read-only diagnostic call used load(path) rather than load(root,path),
raising TypeError/exit1 before inspection. Corrected same bounded diagnostic
printed only file/schema paths/validator names and exited0. No repository files
were changed by diagnosis. Repair only the current mutable cursor; keep all
journal/evidence/history and validator rules intact. Product suite227pass remains
valid but does not substitute for the failed progress gate.
