# IP-25 Evidence - Verified BodyKeeper Transaction

Date: 2026-09-26

## Verified

- BodyKeeper serializes complete control bodies using one canonical JSON representation; append/prepend mutation is not used.
- Local body schema validation occurs before any remote write.
- Canonical state-machine body-writer ownership is enforced before mutation.
- Optional fencing binds object ID, logical object, state, operation ID, and generation before write.
- Text replacement uses the observed version token as a precondition.
- Remote readback is parsed, schema-validated, and SHA-256 verified before success is returned.
- Delayed visibility retries readback only; it does not repeat the body mutation.
- An AMBIGUOUS body mutation is reconciled by readback and is never blindly replayed.
- Persistent schema-invalid readback and persistent hash mismatch are reported separately.
- Fence validity is checked again after verified readback so a stale worker cannot claim success after ownership changed.
- Control body size is hard-bounded.
- BodyKeeper never performs the dependent next-state transition.
- GitHub Actions CI run `36199134649` completed successfully for commit `43637504e2ac28a6dcbaf138e3035d666d873f74`.

## Result

IP-25 completion criteria are satisfied.
