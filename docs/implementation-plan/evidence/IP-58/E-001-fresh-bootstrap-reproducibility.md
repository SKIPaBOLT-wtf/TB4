# IP-58 Evidence — Fresh Bootstrap and Reproducibility

## Verified revision

- Commit: `88c455aa6f4e1a0a4a4389cdb75003dae3c1c772`
- GitHub Actions run: `36274962221`
- CI conclusion: **success**

## What was added or corrected

- `docs/REPRODUCIBILITY.md`
- `config/examples/watchdog.toml.example`
- `config/examples/fetcher.toml.example`
- `tests/reproducibility/test_fresh_bootstrap.py`
- demo bootstrap no longer requires conversation-only knowledge of the in-memory root ID
- existing explicit-root behavior remains supported

## Objective checks

GitHub Actions completed all CI phases successfully:

- clean checkout;
- Python 3.11 setup;
- editable package installation;
- public repository security scan;
- full pytest suite.

The fresh reproducibility path additionally verifies:

- public-safe example TOML parses;
- no private deployment value is required by the examples;
- `python tools/bootstrap_drive.py --demo-memory` succeeds without supplying a root ID;
- a synthetic target completes a job as `FETCH_BALL_DONE`;
- the result can be consumed and recycled to `FETCH_BALL_READY`.

## Boundary

This evidence proves public-repository reproducibility and synthetic bootstrap. It does not claim real private Google Drive, WOL, SSH, or two-machine operation; those belong to IP-59 and IP-60.
