# IP-31 Evidence - Inline Command Runner

Date: 2026-09-26

## Verified

- Small inline commands execute locally through an explicit interpreter family and never use SSH command construction.
- stdout and stderr are read incrementally by separate readers and only bounded tails are retained.
- Unicode output is decoded safely.
- Nonzero exit remains execution evidence and is not prematurely classified as a TB4 terminal result.
- Timeout and cancellation attempt process-group/process-tree termination.
- Forced termination is distinguished from normal termination, and termination failure has an explicit disposition.
- START_FAILED is returned when the configured interpreter/process cannot start.
- EXEC is rejected for free-form inline text rather than guessing argument splitting.
- Script-file requests are rejected by the inline runner.
- GitHub Actions CI run `36240853569` completed successfully for commit `d27a43bd2be13b32ca05edfcca91d9e40e49e740`.

## Result

IP-31 completion criteria are satisfied.
