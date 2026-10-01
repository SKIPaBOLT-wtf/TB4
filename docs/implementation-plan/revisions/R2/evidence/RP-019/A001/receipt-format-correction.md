# RP019 immutable receipt format correction

Original C1.json through C4.json and reviewed-validation.md remain byte-for-byte preserved. Their successful test observations/source11e65c3a5d70e5a8ab8c264cf4d2477126642ef4, INTENT0019 and OUTCOME0027 do not change. Active C1-C4-format-corrected.json receipts encode negative_cases as the schema-required array and include this correction link; all other recorded facts are identical.

Final review discovered trailing blank lines in ten files. The format-only source update removes only extra terminal newlines. Earlier working-tree diff success is not a base-to-head cleanliness claim. Exact stripped-EOF byte and Python AST equality plus real ledger/history/privacy/base-diff verification must pass before merge; the existing runtime/package receipts remain tied to source11e65c3 and tested merge25511f0. No runtime behavior or test expectation changes and no new runtime success is asserted.
