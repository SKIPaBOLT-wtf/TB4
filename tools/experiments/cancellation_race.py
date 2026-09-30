"""RP-014 deterministic fake-process diagnostic. No subprocess or network is opened."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from tb4.core.retry import RetryPolicy
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.drive.state_walker import StateWalker
from tb4.fetcher.cancellation import StopBallCancellation
from tb4.fetcher.execution_models import ExecutionRequest, ExecutionSource, Interpreter
from tb4.fetcher.result_judge import judge_result, ResultClassificationError
import tb4.fetcher.subprocess_runner as runner_module
import tb4.platform.windows_process as windows_process


ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = {
    "natural-control": (0.3,0,10,0,None),
    "late-cancel-zero": (1,0,10,2,"match"),
    "late-cancel-nonzero": (1,7,10,2,"match"),
    "timely-cancel": (2,0,10,0.25,"match"),
    "stale-cancel": (0.3,0,10,0.1,"stale"),
    "runtime-blocked": (10,0,1,2,None),
    "runtime-natural-during-wait": (1.5,0,1,2,None),
    "exit-before-first-check": (0,0,10,0,"match"),
    "exit-before-signal": (1,0,10,0.25,"match"),
    "termination-fails": (10,0,10,0.25,"match"),
}


class Clock:
    def __init__(self):
        self.now = 0.0
        self.trace = []
        self.child = None
        self.heartbeat_ticks = 0

    def log(self,event,**facts):
        assert len(self.trace) < 256, "TRACE_BOUND"
        self.trace.append(dict(at=round(self.now,6),event=event,**facts))

    def monotonic(self): return self.now
    def epoch(self): return 1700002001 + int(self.now)
    def advance(self,seconds):
        self.now = round(self.now + seconds,6)
        self.heartbeat_ticks = int(self.now / 0.25)
        if self.child is not None: self.child.update()


class Stream:
    def __init__(self, child, stderr=False): self.child,self.stderr,self.read_once=child,stderr,False
    def read(self,size):
        if self.read_once: return b""
        self.read_once = True
        return b"" if self.stderr else ("\n".join(self.child.markers)+"\n").encode()
    def close(self): pass


class Reader:
    """Deterministic drain on join; does not model native pipe/thread scheduling."""
    def __init__(self, *, target,args,kwargs,daemon): self.call=lambda:target(*args,**kwargs)
    def start(self): pass
    def join(self,timeout): self.call()


class Child:
    pid = 987654321  # Never passed to an OS API; fake adapters verify this identity.
    def __init__(self, clock, natural_at, code):
        self.clock,self.natural_at,self.natural_code=clock,natural_at,code
        self.returncode=None
        self.markers=["PRE_WAIT"]
        self.stdout,self.stderr=Stream(self),Stream(self,True)
        clock.child=self
        clock.log("started",marker="PRE_WAIT")
        self.update()

    def update(self):
        if self.returncode is None and self.clock.now >= self.natural_at:
            self.returncode=self.natural_code
            self.markers.append("POST_WAIT")
            self.clock.log("natural_exit",exit_code=self.returncode,occurred_at=self.natural_at)

    def poll(self): self.update(); return self.returncode
    def wait(self,timeout):
        if self.poll() is None:
            self.clock.advance(timeout)
            if self.poll() is None: raise subprocess.TimeoutExpired("synthetic",timeout)
        return self.returncode


def cancellation(clock, mode):
    backend=InMemoryDriveBackend()
    fetch_body=json.loads((ROOT / "protocol/examples/fetch-ball/inline-toss.json").read_text(encoding="utf-8"))
    fetch_body.update(generation=11,operation_id="synthetic-job",started_at=1700002001)
    fetch=backend.create_text(backend.root_id,"FETCH_BALL_CHEW",json.dumps(fetch_body))
    fetch_id=fetch.value.metadata.object_id
    body=json.loads((ROOT / "protocol/examples/stop-ball/requested.json").read_text(encoding="utf-8"))
    body.update(fetch_ball_object_id=fetch_id,job_id="synthetic-job",generation=11,expires_at=1700003000)
    stop=backend.create_text(backend.root_id,"STOP_BALL_REQUESTED",json.dumps(body))
    stop_id=stop.value.metadata.object_id
    policy=RetryPolicy((0.01,0.02,0.04),3)
    monitor=StopBallCancellation(backend,StateWalker(backend,policy,clock.monotonic,clock.advance),
        BodyKeeper(backend,policy,clock.monotonic,clock.advance),stop_id,fetch_id,
        "synthetic-job",12 if mode=="stale" else 11,clock.monotonic,clock.epoch)
    return monitor,backend,stop_id


def run_scenario(scenario, platform):
    if scenario not in SCENARIOS or platform not in {"windows","posix"}:
        raise ValueError("UNKNOWN_SYNTHETIC_SCENARIO")
    natural_at,code,limit,delay,mode=SCENARIOS[scenario]
    clock=Clock()
    monitor,backend,stop_id=cancellation(clock,mode) if mode else (None,None,None)
    child=None
    checks=0

    def popen(**kwargs):
        nonlocal child
        assert kwargs["args"] == ["synthetic-no-executable"]
        assert child is None, "NO_REPLAY"
        child=Child(clock,natural_at,code)
        return child

    def check_cancel():
        nonlocal checks
        checks += 1
        clock.log("provider_check_begin")
        if checks==1: clock.advance(delay)
        answer=monitor.should_cancel() if mode else False
        clock.log("provider_check_end",cancel_requested=answer,
                  ack_code=monitor.last_report.ack_code if monitor and monitor.last_report else None)
        return answer

    def signal_fake(pid, sig):
        assert child is not None and pid==child.pid
        clock.log("signal_attempt",signal=sig,alive=child.poll() is None)
        if scenario=="termination-fails": raise OSError("SYNTHETIC_DENIED")
        child.returncode=-sig
        clock.log("signal_exit",exit_code=child.returncode)

    def windows_terminate(process,*,grace_s):
        assert process is child
        try: signal_fake(process.pid,15)
        except OSError: return SimpleNamespace(stopped=False,forced=False,message="SYNTHETIC_DENIED")
        return SimpleNamespace(stopped=True,forced=False,message=None)

    class ObservedRunner(runner_module.SubprocessRunner):
        def _terminate(self,process,*,requested):
            if scenario=="exit-before-signal" and process.poll() is None:
                clock.advance(1)
            clock.log("termination_enter",requested=requested.value,already_exited=process.poll() is not None)
            return super()._terminate(process,requested=requested)

    fake_subprocess=SimpleNamespace(Popen=popen,DEVNULL=-3,PIPE=-1,
        CREATE_NEW_PROCESS_GROUP=512,TimeoutExpired=subprocess.TimeoutExpired)
    fake_os=SimpleNamespace(name="nt" if platform=="windows" else "posix",environ={},killpg=signal_fake)
    with ExitStack() as stack:
        stack.enter_context(patch.object(runner_module,"subprocess",fake_subprocess))
        stack.enter_context(patch.object(runner_module,"os",fake_os))
        stack.enter_context(patch.object(runner_module,"signal",SimpleNamespace(SIGTERM=15,SIGKILL=9)))
        stack.enter_context(patch.object(runner_module,"time",SimpleNamespace(sleep=clock.advance)))
        stack.enter_context(patch.object(runner_module,"threading",SimpleNamespace(Thread=Reader)))
        stack.enter_context(patch.object(windows_process,"terminate_windows_process_tree",windows_terminate))
        request=ExecutionRequest(ExecutionSource.INLINE,Interpreter.PYTHON,limit,inline_command="synthetic")
        report=ObservedRunner(monotonic_now=clock.monotonic)._run_argv(
            request,["synthetic-no-executable"],cancel_requested=check_cancel)
    try:
        classification=judge_result(report).terminal.value
    except ResultClassificationError:
        classification="UNTRUSTWORTHY_TERMINATION"
    stop_body=json.loads(backend.read_text(stop_id).value.text) if backend else {"ack_code":None}
    return dict(scenario=scenario,platform_model=platform,scope="SYNTHETIC_ONLY_NO_PROCESS_OR_NETWORK",
        requested_cancel=mode is not None,ack_code=stop_body["ack_code"],
        stop_state=backend.get_metadata(stop_id).value.name if backend else None,actual_exit_code=child.returncode,
        report_disposition=report.disposition.value,reported_exit_code=report.exit_code,
        classification=classification,markers=report.stdout.splitlines(),
        signal_attempts=sum(row["event"]=="signal_attempt" for row in clock.trace),
        local_runtime_limit_s=limit,finished_s=report.finished_monotonic_s,
        independent_heartbeat_model_ticks=clock.heartbeat_ticks,
        child_still_active=child.poll() is None,trace=clock.trace)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario",choices=(*SCENARIOS,"all"),default="all")
    parser.add_argument("--platform",choices=("windows","posix","all"),default="all")
    args=parser.parse_args(argv)
    names=SCENARIOS if args.scenario=="all" else [args.scenario]
    platforms=("windows","posix") if args.platform=="all" else [args.platform]
    print(json.dumps([run_scenario(s,p) for s in names for p in platforms],sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
