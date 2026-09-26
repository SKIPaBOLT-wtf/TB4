# IP-30 Evidence - RUNNER Interface

Date: 2026-09-26

## Verified

- ExecutionRequest and ExecutionReport provide a transport-independent local execution contract.
- Requests distinguish bounded inline execution from verified local script-file execution.
- Script-file requests require an explicit interpreter family and cannot also contain inline command text.
- RUNNER has no Google Drive, FETCH_BALL, PARK_MAP, or protocol-transition API.
- Process-tree termination is a separate platform boundary.
- Execution reports distinguish EXITED, TIMED_OUT, CANCELLED, START_FAILED, and TERMINATION_FAILED without prematurely assigning TB4 DONE/PARTIAL/FAILED semantics.
- Non-exit reports cannot invent an exit code; START_FAILED cannot claim process start.
- Known side effects are bounded evidence fields rather than inferred promises.
- Environment keys are validated and duplicate/malformed entries are rejected.
- Deterministic FakeRunner proves the interface contract independently of subprocess implementation.
- GitHub Actions CI run `36240794802` completed successfully for commit `4a3c2a15fdb5512041135324301be50c4365b7cd`.

## Result

IP-30 completion criteria are satisfied.
