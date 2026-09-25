# IP-12 Evidence - WAKE_BONE and STOP_BALL Body Schemas

Date: 2026-09-26

## Verified

- `protocol/schemas/wake-bone.schema.json` defines compact wake/bootstrap request and result bodies.
- Wake requests identify a target device and requested FETCHER start behavior without carrying credentials.
- Credential-like fields such as passwords, private keys, tokens, and credentials are explicitly rejected.
- Wake DONE requires confirmed FETCHER pulse evidence.
- Wake FAILED requires a bounded reason code and terminal integrity evidence.
- Structural zero-expiry is rejected; comparison against current time is intentionally reserved for runtime DeadlineGuard.
- `protocol/schemas/stop-ball.schema.json` binds cancellation to exact `fetch_ball_object_id`, `job_id`, and inherited `generation`.
- STOP_BALL acknowledgement requires timestamp and terminal integrity evidence.
- Canonical positive fixtures exist for WAKE_BONE TOSS/DONE/FAILED and STOP_BALL REQUESTED/ACKNOWLEDGED.
- Negative tests cover credential leakage, invalid wake completion, invalid expiry structure, missing exact cancellation identity, and incomplete acknowledgement.
- GitHub Actions CI run `36197479876` completed successfully for commit `fc5e9220e9ee8d10c5c7b84639e974b685a738c5`.

## Result

IP-12 completion criteria are satisfied.
