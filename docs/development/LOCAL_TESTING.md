# Isolated local validation preconditions

Use the repository's isolated environment and Python 3.11. Invoking its Python
by exact path does not automatically activate that environment for subprocesses.
Legacy FETCHER tests resolve the requested interpreter through PATH; a Windows
application-execution alias can exist but return 9009 instead of running Python.
RP-011 A001/DEF-013 preserves that observed failure.

For bounded synthetic tests, prepend the existing virtualenv Scripts directory
only to the current process PATH and verify that Python resolves to that exact
environment. Set PYTHONUTF8=1 for that process and inherited synthetic children,
consistent with native Windows CI. Do not change global PATH, machine aliases,
real interpreter bindings, services or profiles to make tests pass.

Use python -X utf8 -m tools.development.ledger --base <public ownership SHA>.
The CLI has no validate subcommand. UTF-8 must also govern Git subprocess decoding
on Windows; default locale decoding can produce false evidence-byte mismatches.

Choose a new, nonexistent pytest --basetemp under the verified task work directory.
Never delete shared pytest-current or unrelated temporary roots to repair a test
run. Validate the resolved absolute boundary before pytest creates its directory.
Capture each child exit code; a later successful shell command does not establish
that earlier tests or Git fetch succeeded. Stop source-dependent work after a failed
fetch or switch; independently verify the same remote/commit before retrying.

For exact node IDs use python -m pytest <targets> -o addopts='' --collect-only -q.
Combining configured -q with another -q can return grouped file counts instead.
These environment procedures qualify synthetic development tests only, not real
deployed interpreter capability, OS credentials, network or launcher behavior.
