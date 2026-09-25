# IP-11 Evidence - FETCH_BALL Body Schema

Date: 2026-09-26

## Verified

- `protocol/schemas/fetch-ball.schema.json` extends the common control envelope without duplicating lifecycle filename state.
- Inline and artifact payload sources are mutually exclusive.
- Inline payloads are bounded to 8192 characters; larger scripts are forced toward TOY_BOX artifact transport.
- Runtime hints are public-safe bounded strings rather than deployment-specific commands.
- Terminal results preserve operation identity and generation through the common envelope.
- Terminal results require `finished_at` and `result_sha256`.
- `PARTIAL` requires non-empty completed-effect evidence and may not claim unknown effects.
- `GONE` requires `effects_known = UNKNOWN` and cannot invent an exit code.
- Canonical fixtures exist for inline request, artifact request, CHEW, DONE, PARTIAL, FAILED, CANCELLED, and GONE.
- Negative tests cover ambiguous payload source, oversized inline payload, missing PARTIAL evidence, invalid GONE semantics, missing terminal identity evidence, lifecycle-state duplication, and unknown body fields.
- GitHub Actions CI run `36197357001` completed successfully for commit `e0e12afab925415eca23c11db7873277d60b4189`.

## Result

IP-11 completion criteria are satisfied.
