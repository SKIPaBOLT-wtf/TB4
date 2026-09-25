# IP-31 - Inline Command Runner

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Implement safe execution for small bounded commands without reverting to remote giant command lines.

## Preconditions

IP-30 VERIFIED.

## Inputs / authoritative references

- `RUNNER contract`
- `job inline-size limits`

## Work

1. Implement local subprocess invocation with explicit argument/interpreter mode.
2. Capture bounded stdout/stderr incrementally.
3. Track start/finish/exit code.
4. Implement timeout termination of child process tree where platform primitives allow.
5. Return ExecutionReport without classifying TB4 terminal state.

## Files / modules

- `src/tb4/fetcher/subprocess_runner.py`
- `tests/fetcher/test_inline_runner.py`

## Required invariants

- Inline payload size is bounded before RUNNER receives it.
- No SSH quoting/remote-shell construction occurs here.

## Tests

- Successful command.
- Nonzero exit.
- stdout/stderr.
- Timeout.
- Unicode output.
- Bounded capture.

## Failure cases

- Child process survives required termination.
- Output capture can consume unbounded memory.

## Completion evidence required

- Inline runner tests pass on supported development platform.

## Handoff state

Small commands can execute locally through FETCHER.

## Amendment path

`docs/implementation-plan/amendments/IP-31/`

## Evidence path

`docs/implementation-plan/evidence/IP-31/`
