# One-line root-plan records nesting repair

Source `4fa196601cbb201a779334808c0f6c4f9aff8cdc`; base application source `5b9c339e06d91822c594dca6f276f6634dd2dc48`. Only `src/tb4/reconfiguration_roots.py` changed: the denial-only begin preflight reads `document()["records"][SLOT]` instead of the top-level slot. Exact diff and safe publication reviewed; all839 original test predicates unchanged. Local source commit `88261aef13abaee79003512853f465af6edef7a4` retained separately; public source readback verified.

No owner/C1/C2/native/effects/SDK/first-run guard, schema, budget or runtime access change. Source-only checkpoint is not acceptance. Next: explicit partial fast original root-related8-target check (exclude only the costly129-object capacity predicate), then full same36-target839-case qualification with that original capacity fixture and all native cases.
