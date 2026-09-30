# RP-014 / A001 reviewed cancellation reproduction

Source: `b22cc63fc4424ba3cd21c664a8a1de3cf59b2e58`. Test head: `91ea2a413d282e707d4f249b1b0754fd83094bcc`.
PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/22 . Base: `e537bab0076f7b4943aeddc75f8c73275c38e910`.
Scope is deterministic diagnostic handoff only. DEF-002 and issue7 remain OPEN, with historical proven_origin null. No live process, network, runtime deployment, installer or previous workload was used by the experiment.

## Reproduction and separate evidence axes

Ran `python -X utf8 -m tools.experiments.cancellation_race --scenario all --platform all`: exit0, twenty bounded synthetic schedules. Full reviewed output is in synthetic-scenario-traces.json. Both platform branches have identical classifications; denied termination attempts differ (Windows2, POSIX4) because the actual runner applies platform-specific fallback and its defensive final attempt. The table shows Windows; all twenty complete traces are retained.

| Schedule | ACK | Signal attempts | Actual / reported exit | Disposition | Markers | Finish seconds |
|---|---|---:|---|---|---|---:|
| natural-control | none | 0 | 0 / 0 | EXITED | PRE_WAIT, POST_WAIT | 0.3 |
| late-cancel-zero | CANCEL_SIGNALLED | 0 | 0 / none | CANCELLED | PRE_WAIT, POST_WAIT | 2 |
| late-cancel-nonzero | CANCEL_SIGNALLED | 0 | 7 / none | CANCELLED | PRE_WAIT, POST_WAIT | 2 |
| timely-cancel | CANCEL_SIGNALLED | 1 | -15 / none | CANCELLED | PRE_WAIT | 0.25 |
| stale-cancel | NO_MATCH | 0 | 0 / 0 | EXITED | PRE_WAIT, POST_WAIT | 0.3 |
| runtime-blocked | none | 1 | -15 / none | TIMED_OUT | PRE_WAIT | 2.05 |
| runtime-natural-during-wait | none | 0 | 0 / 0 | EXITED | PRE_WAIT, POST_WAIT | 2.05 |
| exit-before-first-check | none | 0 | 0 / 0 | EXITED | PRE_WAIT, POST_WAIT | 0 |
| exit-before-signal | CANCEL_SIGNALLED | 0 | 0 / none | CANCELLED | PRE_WAIT, POST_WAIT | 1.25 |
| termination-fails | CANCEL_SIGNALLED | 2 | none / none | TERMINATION_FAILED | PRE_WAIT | 0.25 |

These are simulated exits/signals: every Popen/OS/time adapter is scoped and replaced, one fake child per scenario, no OS process/PID is operated. Natural-exit trace records both observation time and modeled occurrence. Reader fixtures drain on join, not native concurrent pipes. Heartbeat counter is labeled a model. Separate event-controlled real-thread test exercises the actual _HeartbeatExecutor wrapper: inner execution proceeds while a provider tick is pending, then releases/joins within its bounded fixture.

The actual SubprocessRunner loop reads monotonic time before synchronous cancellation I/O. Its _terminate returns the requested disposition if the process has already exited. The runner drops real exit0/7; result judge trusts CANCELLED. STOP_BALL CANCEL_SIGNALLED is persisted before any signal. Runtime1s first signals2.05s after provider wait; natural exit1.5s during that wait escapes the local deadline and reports DONE. Timely cancellation, stale generation, initial natural exit and denied termination provide independent controls. This causality is proved for current-source paths, not attributed to the historical installed binary.

## Check mapping

- C1: ten fixed schedules per platform, deterministic time and PRE_WAIT/POST_WAIT; no child replay.
- C2: request/ACK, termination entry, signal attempts, actual exit, reported exit, disposition and classification are separately asserted and recorded.
- C3: strict expected failures demonstrate two required invariants are currently violated on both modeled platforms. They are repair handoff, not passing runtime acceptance. Independent heartbeat cannot hide local starvation or establish interruption.
- C4: DEF-002 retains original history and OPEN status, adds these reproductions/hypotheses and the regression. RP-044/045/046 must preserve actual natural exit, isolate monotonic local supervision from provider work, bound cancellation cache and verify native process trees/output. Issue7 remains open; publication recovery cannot close it.

## Exact validation

Windows Python3.11, process-local venv PATH/PYTHONUTF8 and PYTHONPATH=src, fresh task-owned nonexistent pytest basetemp. Command targets: `python -X utf8 -m pytest tests/integration/test_cancellation_race_reproduction.py tests/integration/test_result_publication_reproduction.py tests/integration/test_google_transactions.py tests/drive tests/fetcher tests/feasibility tests/protocol tests/development --basetemp <fresh-task-temp> -ra`.

Observed exit0: **911 passed, 2 skipped, 5 xfailed in23.29s**. Exact collection:918 nodes in0.42s, saved in local-collected-nodes.txt. New diagnostic adds47 cases:43 pass and4 strict expected failures. Other expected failure is retained RP-013 benign metadata regression. Skips: POSIX file-mode assertion (Windows native ACL qualification RP-020) and POSIX SIGTERM-ignore behavior. No skip counted as a passing platform gate.

Linux full CI: [run36792713861](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36792713861), job110149066921, merge86c3054 of exact test head into ownership base: **1328 passed, 2 skipped, 5 xfailed in17.95s**, all steps PASS including public scan. [Progress36792713775](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36792713775), job110149066420: development tests, ledger, published-history preservation and scanner PASS. No runtime/protocol/package changes; Desktop build is not triggered/required for this diagnostic-only scope.

Local ledger base ownership: PASS/13 previously verified/only current validation pending. Diff whitespace clean. Initial direct scanner invocation omitted PYTHONPATH and exited1 ModuleNotFoundError before any scan; rerun with documented PYTHONPATH=src exited0 clean. A guessed schema read path was absent; no schema change made. One oversized capture was tool-truncated and rejected before JSON parsing; three bounded file reads recovered original persisted outputs without rerunning tests/diagnostics.

## Review, privacy and limits

Reviewed source, actual runner/monitor/judge paths, all assertions and retained traces. All identities/payloads are synthetic; CLI rejects PID/host/token/replay arguments. No raw provider data or credentials. No source changes to live runner, no production behavior change, no amendment of old accepted evidence. Strict xfails remain discoverable required failures until later implementations have reviewed native proof; counts alone do not accept corrected behavior.

Native Windows/POSIX termination, descendant ownership, blocked pipes/output capture completeness, actual remote cancellation latency, unknown termination handling and terminal publication/consume/READY remain later gates. Rollback removes diagnostic additions only; a fake logically active child has no OS resource to kill. Never use its numeric PID on a host or replay an old generation.
