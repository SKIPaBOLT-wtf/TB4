# TB4 Agent Entry Point

## Current development direction - 2026-09-30

Read `docs/DEVELOPMENT_REALIGNMENT_PROMPT.md` before selecting further development
work. It records the owner's corrected target, the source audit, necessary logical
corrections and open decisions. This is a documentation-only checkpoint: do not
resume the old pilot/fix loop or create a detailed implementation plan until the
owner explicitly requests the next phase. Existing protocol files still govern
installed software; the realignment prompt does not authorize live state changes.
Historical plan statuses and evidence are unchanged.

Then read these files in order:

1. `docs/START_HERE.md`
2. `docs/execution-contract/README.md`
3. `docs/implementation-plan/README.md`
4. the current implementation-plan step named by `docs/implementation-plan/manifest.yaml`

Rules:

- The repository is authoritative project memory.
- Do not invent protocol states or rename canonical dog/ball vocabulary casually.
- Normal control paths must prefer exact stable object identities over folder scans.
- Repeated mechanical behavior belongs in deterministic helpers.
- Keep public source free of private deployment details and secrets.
- Do not skip ahead in the implementation plan.
- Do not mark a step complete without its required evidence.
