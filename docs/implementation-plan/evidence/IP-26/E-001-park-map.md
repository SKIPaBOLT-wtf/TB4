# IP-26 Evidence - PARK_MAP Index Model

Date: 2026-09-26

## Verified

- PARK_MAP has a versioned JSON Schema and immutable Python model.
- Logical references map directly to stable backend object IDs.
- Required global references and the complete per-device control subtree fail closed when missing.
- Duplicate object IDs, including accidental reuse of the root ID, are rejected.
- Device identity uses stable `device_id`; `device_key` remains a separate registration/folder attribute and may change without changing object identity.
- Exact device lookups use deterministic logical references and never fall back to folder scanning.
- Replacing one verified reconstructable child requires the expected old object ID, rejects adoption of an ID already owned elsewhere, increments `map_generation`, and leaves unrelated references unchanged.
- Device registration requires the complete canonical reference set and unique object IDs.
- Unsupported schema/protocol versions are rejected.
- GitHub Actions CI run `36199308655` completed successfully for commit `bd3b54c628a692395f4eca13c969ce169f388d64`.

## Result

IP-26 completion criteria are satisfied.
