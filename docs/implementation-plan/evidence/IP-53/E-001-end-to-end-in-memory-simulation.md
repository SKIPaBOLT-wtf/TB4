# IP-53 Evidence — End-to-End In-Memory Simulation

## Verified capability

The in-memory integration harness exercises the production TB4 transaction and orchestration layers without real Google Drive or LAN dependencies.

Verified scenarios in `tests/integration/test_end_to_end_simulation.py`:

- awake target direct job;
- sleeping target wake then job;
- two independent target work streams;
- partial result;
- cancelled execution;
- target loss terminalized as `FETCH_BALL_GONE`.

The simulation asserts that normal runtime flows do not call `list_children()`.

## Authoritative CI evidence

- Commit: `3fdbe89e799e7cfacdaa618c868337ffa40a26c3`
- GitHub Actions workflow: `CI`
- Run: `#332`
- Run ID: `36269269884`
- Job: `test`
- Result: `success`
- The workflow installs the package and executes the full `pytest` suite.
- The `Test` step completed successfully.

Run URL: https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36269269884

## Completion assessment

IP-53 completion criteria are satisfied:

- production helpers are used by the simulation harness;
- deterministic fake clock/network/executor components are used only at external boundaries;
- sleeping wake flow is covered;
- FETCH_BALL dispatch/claim/terminal/recycle flow is covered;
- per-device independence is covered;
- partial/cancel/loss terminal states are covered;
- exact-object behavior is asserted through zero runtime `list_children` calls.
