# IP-32 Evidence — Script Artifact Runner

## Verified capability

The FETCHER script-artifact path materializes verified artifact bytes into an implementation-controlled temporary directory, re-verifies the local bytes, selects only an allow-listed interpreter family, executes the local script file without reconstructing the script into a giant remote command line, captures an `ExecutionReport`, and cleans temporary files by default.

## Evidence

- Implementation: `src/tb4/fetcher/artifact_runner.py`
- Shared subprocess execution: `src/tb4/fetcher/subprocess_runner.py`
- Focused tests: `tests/fetcher/test_artifact_runner.py`
- Final fix commit: `5a0b5af32b825fcbfb26ba3290789747e4ec9016`
- GitHub Actions run: `36240956843`
- CI conclusion: **success**

The focused tests cover:

- large multiline script execution from a local temporary file;
- exact descriptor-object identity enforcement;
- hash mismatch rejection before materialization;
- interpreter/suffix mismatch rejection;
- expired artifact rejection;
- local size-policy enforcement;
- timeout cleanup;
- cancellation cleanup;
- hostile remote identifiers never becoming local filesystem paths.

## Completion criteria

The large multiline script path executes without embedding the script into a shell/SSH command line, artifact integrity is checked before execution and again after local materialization, and CI is green.

**Result: VERIFIED.**
