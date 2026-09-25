# IP-18 Evidence - State Transition Validator

Date: 2026-09-26

## Verified

- Canonical state machines are loaded from `protocol/state-machines.yaml` and cached by resolved path.
- Runtime transition validation returns explicit LEGAL, IDEMPOTENT, or ILLEGAL disposition.
- Every canonical edge is accepted for every actor explicitly registered on that edge.
- Known actors not registered for an edge are rejected.
- Same-state requests are distinguishable as idempotent rather than new transitions.
- Unknown object/state/actor inputs are rejected.
- Terminal-state classification exactly matches canonical YAML.
- The validator is pure and contains no Drive/network mutations.
- CI initially caught a faulty test assumption about multi-actor edges; the test was corrected to evaluate the complete actor set for each canonical edge.
- GitHub Actions CI run `36198258724` completed successfully for commit `281022201017bb906c96c1f68362ff8113719b40`.

## Result

IP-18 completion criteria are satisfied.
