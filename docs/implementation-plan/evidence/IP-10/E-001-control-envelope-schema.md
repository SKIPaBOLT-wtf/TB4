# IP-10 Evidence - Common Control Envelope Schema

Date: 2026-09-25

## Verified

- Live control bodies use complete UTF-8 JSON replacement/readback rather than append/prepend mutation.
- Lifecycle state is authoritative in the Drive filename; body keys `state`, `lifecycle_state`, and `filename_state` are forbidden.
- Common fencing and timing fields are defined:
  - `generation`
  - `operation_id`
  - `given_at`
  - `expires_at`
  - `started_at`
  - `finished_at`
  - `run_limit_s`
- Payload/result integrity fields use lowercase SHA-256 or null.
- Artifact references are bounded and include stable ID, kind, byte size, and SHA-256.
- A hard protocol ceiling exists for `run_limit_s`.
- JSON Schema draft 2020-12 validation tests cover valid body, missing generation, invalid hash, forbidden lifecycle state in body, artifact references, operation-id characters, and runtime ceiling.
- GitHub Actions CI run `36194844037` completed successfully for commit `3ea8474abfb7a2b3bcd76d1b05c42724866e1103`.

## Result

IP-10 completion criteria are satisfied.
