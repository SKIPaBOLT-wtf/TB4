# IP-24 Evidence - Verified StateWalker Rename Transaction

Date: 2026-09-26

## Verified

- StateWalker reads exact metadata by stable object ID and never lists folders on the normal path.
- Canonical transition legality and actor ownership are checked before any rename.
- Optional fencing rejects stale generation and mismatched ownership before mutation.
- Rename uses the observed version token as a precondition.
- Successful rename is remotely confirmed using bounded exact-ID metadata probes.
- Delayed visibility confirms without issuing a second rename.
- AMBIGUOUS rename is reconciled only by exact-ID reads and is never automatically replayed.
- True TRANSIENT_ERROR may consume the next bounded mutation attempt.
- Wrong expected state, illegal transition, stale fence, and precondition conflict stop before dependent work.
- StateWalker performs no body writes.
- The initial CI failure was test-only: absent operation-counter keys were correctly interpreted as “operation never occurred” after assertions were fixed to use zero defaults.
- GitHub Actions CI run `36198955854` completed successfully for commit `f24311963c8174403199c8a004a37efcf3f6bd24`.

## Result

IP-24 completion criteria are satisfied.
