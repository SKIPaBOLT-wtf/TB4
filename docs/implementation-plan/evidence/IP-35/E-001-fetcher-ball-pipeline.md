# IP-35 Evidence — FETCHER Ball Claim and Return Pipeline

## Verified capability

The single-job FETCHER pipeline now:

- addresses one exact FETCH_BALL object ID;
- validates TOSS body/schema and expiry before claim;
- claims TOSS -> CHEW through StateWalker;
- writes started_at only after CHEW is remotely confirmed;
- executes through a local execution boundary;
- moves CHEW -> RETURNING before writing terminal evidence;
- writes and remotely verifies the terminal body through BodyKeeper;
- publishes DONE/PARTIAL/FAILED/CANCELLED only after verified result-body readback;
- uses operation/generation fencing at every dependent state/body mutation;
- rejects a stale worker if a newer generation appears during execution;
- does not list PLAYGROUND on the normal path.

## Evidence

- Implementation: `src/tb4/fetcher/ball_pipeline.py`
- Tests: `tests/fetcher/test_ball_pipeline.py`
- Final test commit: `562d11c7f70bf05db358d37a403033c97c2d9ea4`
- GitHub Actions run: `36242294841`
- CI conclusion: **success**

Focused coverage includes DONE, PARTIAL, FAILED, expired TOSS, stale generation during execution, and delayed Drive claim visibility.

**Result: VERIFIED.**
