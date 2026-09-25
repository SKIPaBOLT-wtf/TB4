# IP-16 Evidence - Protocol Validator CLI

Date: 2026-09-26

## Verified

- `tools/validate_protocol.py` provides one deterministic repository validation command.
- `src/tb4/core/spec_validation.py` validates YAML/JSON/TOML parseability without modifying source files.
- Duplicate YAML and JSON mapping keys are rejected.
- Registered stateful objects are cross-checked against state machines.
- Transition states, actors, body-writer roles, tree logical-object references, and canonical initial filenames are cross-checked.
- Required canonical schemas are validated and missing schemas are reported.
- Configuration rule references are resolved against defaults; FATAL violations fail validation while WARNING violations are reported without forcing failure.
- Multiple independent errors are collected when safe instead of stopping at the first issue.
- CLI exits zero for the canonical repository and nonzero for malformed fixtures.
- GitHub Actions CI run `36198022843` completed successfully for commit `2ea66bc21fb606565697def1af56e2bcd0cff884`.

## Result

IP-16 completion criteria are satisfied.
