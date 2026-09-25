# IP-20 Evidence - Clock and Deadline Helpers

Date: 2026-09-26

## Verified

- UTC epoch time is separated from local monotonic duration measurement.
- Accept expiry, run deadline, lease expiry, and stale-age boundaries are closed and deterministic at exact deadlines.
- Monotonic deadlines remain correct across backward wall-clock jumps.
- Future remote timestamps within configured tolerance never produce negative ages.
- Future timestamps beyond tolerance raise an explicit ClockSkewError instead of being treated as healthy indefinitely.
- Fake-clock tests prove deterministic forward progression.
- Unstarted run/lease values and non-positive thresholds are rejected rather than silently accepted.
- GitHub Actions CI run `36198414122` completed successfully for commit `5d5949580e8e02a565e4bb1b92d83b461d65d720`.

## Result

IP-20 completion criteria are satisfied.
