# IP-57 Evidence — TB4 Skill and COACH Interface

## Verified capability

The AI-facing TB4 control layer now consists of:

- compact Skill source under `skill/tb4/`;
- `docs/COACH.md` operational decision flow;
- `protocol/coach-workflows.yaml` representative machine-readable scenarios;
- regression tests under `tests/coach/`;
- refreshed `docs/START_HERE.md` cold-start path.

The Skill intentionally points to canonical repository/Drive sources instead of bundling a duplicate protocol copy.

## Skill validation/package evidence

Canonical skill tooling was used locally:

- initialized with the canonical `init_skill.py` flow;
- `quick_validate.py`: `Skill is valid!`;
- `package_skill.py`: success;
- package filename: `skill.zip`;
- package contents: `tb4/SKILL.md`, `tb4/references/source-map.md`, `tb4/agents/openai.yaml`;
- package size: ~4 KB;
- SHA-256: `631d046a2f043d63e64553ec9de4b517dd38242f4623e7661a50c74f3a077cec`.

## COACH behavior covered

Regression tests verify:

- Skill metadata and UI metadata;
- progressive source loading;
- FETCH_BALL state names referenced by Skill are canonical;
- representative workflow conditions use canonical state-machine states;
- READY target dispatch flow;
- sleeping target wake-before-dispatch flow;
- exact-job cancellation flow;
- PARTIAL inspection/no implicit replay;
- mutating GONE inspection/no implicit replay;
- DOG_SHIT blocking behavior;
- SSH remains fixed bootstrap only;
- no busy-poll/background-monitoring claims;
- no bundled duplicate protocol schemas/state machines;
- no public-repository security findings in Skill/COACH sources.

## CI evidence

- COACH contract tests commit CI run #364: success
- Current entrypoint commit CI run #365: success
- Run #365: https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36272823136

Both security scan and full pytest passed.

## Completion assessment

IP-57 is complete. A fresh AI can start from the compact TB4 Skill, progressively load canonical project sources, resolve live object IDs from PARK_MAP, and follow deterministic COACH branching without copying the entire protocol into prompt text.
