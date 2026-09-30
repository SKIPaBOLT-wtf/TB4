# RP-014 cancellation and natural-exit reproduction

Diagnostic handoff for DEF-002 and [issue 7](https://github.com/SKIPaBOLT-wtf/TB4/issues/7).
The issue remains open. Historical retained output includes a post-wait marker
despite CANCELLED/CANCELLED_BY_REQUEST and STOP_BALL CANCEL_SIGNALLED. Publication
recovery does not prove interruption. The original initiating timing and installed
binary identity are not established by the new synthetic experiment.

```text
python -X utf8 -m tools.experiments.cancellation_race --scenario all --platform all
python -X utf8 -m pytest tests/integration/test_cancellation_race_reproduction.py -ra
```

The closed CLI accepts fixed scenario/platform names only. It never accepts a PID,
host, token or old operation. No subprocess or network client is opened. Scoped
fake adapters replace process creation, OS signalling and time only inside the
diagnostic. The actual SubprocessRunner loop/_terminate, StopBallCancellation,
StateWalker, BodyKeeper and ResultJudge execute against those controlled facts.
Both Windows and POSIX branches are models; they do not prove native process-tree,
pipe, permission, interpreter or descendant behavior. Fake readers drain on join,
so concurrent native output-pressure qualification remains RP-044/045.

## Independent evidence axes

Each record keeps the request, exact STOP_BALL acknowledgement/state, actual fake
child exit code, emitted PRE_WAIT/POST_WAIT markers, entry into termination,
signal attempts, returned execution disposition/exit code and final classification
separate. One synthetic process is created, trace count is bounded to256, and no
scenario replays it. A modelled independent heartbeat counter is explicitly labelled
as such; it is not a real provider heartbeat observation.

Ten schedules per platform cover ordinary natural completion; exit0 and exit7
during a slow matching cancel check; timely cancellation; stale generation;
runtime expiry while a no-cancel provider check blocks; natural completion beyond
the runtime limit during that wait; exit before the first poll; exit between ACK
and termination; and denied termination. Actual observed outcomes are preserved
with source-linked reviewed evidence, not inferred from a CANCELLED label.

The current code reads monotonic time before calling the synchronous cancellation
callback. While it waits, local polling/runtime checks cannot run. It then acts
on the callback and the old time sample. `_terminate` returns the requested
disposition when its first poll discovers the process has already exited. The
runner consequently drops that real exit code, and ResultJudge receives a
CANCELLED disposition which it trusts. This is a concrete current-source path;
whether it caused the historical live event remains UNKNOWN.

STOP_BALL's CANCEL_SIGNALLED is written before the local signal attempt. It proves
the matching request was acknowledged, not that an OS signal was sent or had any
effect. The timely-cancel control must show signal evidence and no normal POST_WAIT;
the late-cancel counterexample retains POST_WAIT and the actual natural exit.
Denied termination must remain untrustworthy, not a successful cancellation.

The actual `_HeartbeatExecutor` already publishes in a separate thread. A bounded
thread synchronization control verifies its provider tick can remain pending
while inner execution proceeds. Do not blame a synchronous heartbeat path that
does not exist in this source. Independent heartbeat progress cannot establish
that the local timeout loop is responsive while cancellation I/O blocks it.

## Required repair handoff

Strict expected-failure oracles require (on both platform models):

1. A natural exit observed after a slow cancellation check retains EXITED and its
   real exit code; no signal means no claimed interruption. Classify exit0 as DONE
   and nonzero using actual effects under the normal result contract.
2. Local monotonic runtime enforcement does not wait behind provider work; the
   first termination attempt occurs within the declared local sampling bound.

RP-044/045 must rerun these invariants against their native Windows/Linux process
supervisors, independently drain output, preserve process identity and distinguish
requested cancellation, signal attempt, stopped tree and actual exit. Check again
at the signal boundary; polling and sending a signal are not one atomic action.
Evidence must handle natural exit races without fabricating cancellation or
timeout and must expose uncertain/failed termination honestly.

RP-046 must make supervision consume a bounded local cancellation signal/cache
with exact target/operation/generation. Provider reads/ACK writes need their own
bounded transport work. Repeated/stale requests and ambiguous transport must not
act on another process or relabel completed evidence. RP-011's timing profile and
RP-012's unknown-work/capture/authorization gates remain binding.

These strict xfails are an unresolved repair handoff, not passing runtime tests.
Retire/replace them only with reviewed source-linked passing implementations and
native evidence; preserve legacy counterexamples as needed. Actual owned process
trees, signal resistance, blocked output, cancellation latency, terminal
publication, explicit consumption and READY round trip remain later native/live
gates. Do not close DEF-002 or issue7 on diagnostic acceptance, heartbeat activity,
ACK, GUI state or a publication-only recovery.

Rollback removes synthetic additions only. A denied-termination fixture may leave
a fake child logically active; it has no OS resource or PID to kill. Never apply
the fixture's numeric identity to a real process or repeat a prior live generation.
