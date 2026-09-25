# IP-19 Evidence - FenceGuard

Date: 2026-09-26

## Verified

- Fence ownership requires stable object ID, operation ID, generation, and expected logical object state.
- Missing fence components are rejected and never treated as wildcards.
- A worker observing a newer generation is classified STALE and cannot write.
- Object ID, operation ID, same-generation state mismatch, and unexpectedly older observed generation are rejected as MISMATCH.
- Fence comparison and assertion are pure and have no transport side effects.
- Generation advancement is explicitly required to be strictly monotonic for channel reuse.
- Mapping round-trip and stale-generation/stale-job/object mismatch tests pass.
- GitHub Actions CI run `36198334956` completed successfully for commit `5022db8f11f27044431873021c58538334fa6251`.

## Result

IP-19 completion criteria are satisfied.
