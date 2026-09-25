# IP-04 Evidence - FETCH_BALL State Machine

Date: 2026-09-25

## Verified

- Canonical states are defined in `protocol/state-machines.yaml`:
  - READY
  - LOADING
  - TOSS
  - CHEW
  - RETURNING
  - DONE
  - PARTIAL
  - FAILED
  - CANCELLED
  - GONE
  - RECYCLING
- Transition actors are explicit.
- Body-writer ownership is explicit per state.
- `GONE` and `PARTIAL` require effect inspection before retry.
- `TOSS` and `CHEW` use the agreed protocol vocabulary.
- Every state is reachable from READY in the canonical graph.
- Every terminal state has a COACH-owned recycling exit.
- GitHub Actions CI run `36194118265` completed successfully for commit `8fec1ba5316af1d4a81503d1a90c6124a94fc74a`.
- The CI `Test` step completed successfully.

## Result

IP-04 completion criteria are satisfied.
