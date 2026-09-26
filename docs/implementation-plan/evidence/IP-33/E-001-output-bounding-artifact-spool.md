# IP-33 Evidence — Output Bounding and Artifact Spool

## Verified capability

TB4 now preserves complete subprocess output without allowing live control objects or RAM use to grow without an explicit bound.

- `SubprocessRunner` keeps bounded stdout/stderr tails while optionally streaming chunks to an output observer.
- `OutputCapture` spools complete output to controlled local files with a hard total-byte ceiling.
- Small results remain inline.
- Oversized results are serialized into one `RESULT_TEXT` TOY_BOX content object, remotely read back, size/hash verified, then referenced through a descriptor created last and verified by exact object ID.
- Artifact/backend failure raises an explicit error and never fabricates a successful preservation claim.
- Temporary spool files are removed after finalization.

## Evidence

- Implementation:
  - `src/tb4/fetcher/subprocess_runner.py`
  - `src/tb4/fetcher/artifact_spool.py`
- Tests: `tests/fetcher/test_artifact_spool.py`
- Final fixing commit: `4a99b980a7cf1af27314b7a3c2b15c44a626f020`
- GitHub Actions run: `36242065442`
- CI conclusion: **success**
- Suite result after the implementation: all repository tests passed.

## Covered behavior

- inline small output;
- large stdout artifact;
- large stderr plus mixed output;
- descriptor/content SHA-256 verification;
- bounded tails;
- explicit backend failure;
- explicit local spool-ceiling failure;
- cleanup.

**Result: VERIFIED.**
