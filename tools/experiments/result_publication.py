"""Synthetic-only RP-013 reproduction; never opens a credential or network client."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tb4.core.retry import RetryPolicy
from tb4.core.schemas import canonical_json_text
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.google_backend import GoogleDriveBackend
from tb4.drive.state_walker import StateWalker
from tb4.fetcher.artifact_spool import BoundedResult
from tb4.fetcher.ball_pipeline import BallPipeline, BallPipelineError, LocalExecution
from tb4.fetcher.execution_models import ExecutionDisposition, ExecutionReport


SCENARIOS = ("baseline", "benign-version", "stale-precheck", "foreign-before-fence",
             "foreign-after-precheck", "http-409", "http-412", "http-429",
             "lost-reply", "post-apply-version-drift", "stale-result-media")
ROOT = Path(__file__).resolve().parents[2]
OBJECT = "synthetic-publication-object"


class Request:
    def __init__(self, action): self.action = action
    def execute(self): return self.action()


class HttpFailure(Exception):
    def __init__(self, status):
        self.resp = type("Response", (dict,), {"status":status})()
        self.content = b'{"error":{"errors":[]}}'
        super().__init__("synthetic provider failure")


class Clock:
    now = 100.0
    epoch_value = 1700000001
    def monotonic(self): return self.now
    def sleep(self, delay): self.now += delay
    def epoch(self):
        self.epoch_value += 1
        return self.epoch_value


class ControlledFiles:
    """Deterministic exact-object wire fixture used by the actual Google adapter."""
    def __init__(self, scenario):
        if scenario not in SCENARIOS: raise ValueError("UNKNOWN_SYNTHETIC_SCENARIO")
        self.scenario = scenario
        body = json.loads((ROOT / "protocol/examples/fetch-ball/inline-toss.json").read_text(encoding="utf-8"))
        body["inline_payload"] = "synthetic payload never executed"
        body["payload_sha256"] = hashlib.sha256(body["inline_payload"].encode()).hexdigest()
        self.content = canonical_json_text(body).encode()
        self.metadata = dict(id=OBJECT, name="FETCH_BALL_TOSS", parents=["synthetic-parent"],
                             mimeType="text/plain", version="1", size=str(len(self.content)))
        self.trace = []
        self.terminal_attempts = self.terminal_wire_calls = 0
        self.body_writes = 0
        self.next_version = self.stale_media = None
        self.recorded_result = None

    def files(self): return self

    def log(self, event, **values):
        assert len(self.trace) < 256, "SYNTHETIC_TRACE_BOUND"
        self.trace.append(dict(event=event, **values))

    def bump(self): self.metadata["version"] = str(int(self.metadata["version"]) + 1)

    def foreign_generation(self):
        body = json.loads(self.content)
        body["generation"] += 1
        body["operation_id"] = "synthetic-foreign-generation"
        self.content = canonical_json_text(body).encode()
        self.bump()
        self.log("foreign_generation", version=self.metadata["version"])

    def get(self, **kwargs):
        assert kwargs["fileId"] == OBJECT
        def read():
            snapshot = dict(self.metadata)
            if self.next_version is not None:
                snapshot["version"], self.next_version = self.next_version, None
            self.log("metadata", version=snapshot["version"], state=snapshot["name"])
            return snapshot
        return Request(read)

    def get_media(self, **kwargs):
        assert kwargs["fileId"] == OBJECT
        def read():
            result = self.content
            if self.stale_media is not None:
                result, self.stale_media = self.stale_media, None
            self.log("media", generation=json.loads(result)["generation"],
                     sha256=hashlib.sha256(result).hexdigest())
            return result
        return Request(read)

    def update(self, **kwargs):
        assert kwargs["fileId"] == OBJECT
        is_terminal = kwargs.get("body", {}).get("name") == "FETCH_BALL_DONE"
        def apply():
            if is_terminal:
                self.terminal_wire_calls += 1
                self.log("terminal_wire", fields=sorted(kwargs))
                if self.scenario.startswith("http-") and self.terminal_wire_calls == 1:
                    status = int(self.scenario[5:])
                    self.log("provider_rejected", status=status)
                    raise HttpFailure(status)
                if self.scenario == "foreign-after-precheck": self.foreign_generation()
            if "media_body" in kwargs:
                old = self.content
                self.content = kwargs["media_body"]["data"]
                self.body_writes += 1
                if json.loads(self.content).get("result_code") == "DONE":
                    self.recorded_result = self.content
                    if self.scenario == "stale-result-media": self.stale_media = old
            self.metadata.update(kwargs.get("body", {}))
            self.metadata["size"] = str(len(self.content))
            self.bump()
            receipt = dict(self.metadata)
            self.log("applied", version=receipt["version"], state=receipt["name"])
            if is_terminal and self.scenario == "lost-reply": raise TimeoutError("synthetic lost reply")
            if is_terminal and self.scenario == "post-apply-version-drift": self.bump()
            return receipt
        return Request(apply)

    def list(self, **kwargs): raise AssertionError("NO_FOLDER_SCAN")
    def create(self, **kwargs): raise AssertionError("NO_REPLACEMENT_OBJECT")
    def delete(self, **kwargs): raise AssertionError("NO_DELETE")


class ScheduledBackend(GoogleDriveBackend):
    def rename(self, object_id, new_name, *, expected_version_token=None):
        fixture = self.service
        if new_name == "FETCH_BALL_DONE":
            fixture.terminal_attempts += 1
            fixture.log("terminal_attempt", expected_version=expected_version_token)
            if fixture.terminal_attempts == 1:
                if fixture.scenario == "benign-version":
                    fixture.bump()  # Only a provider metadata change; same body/owner/state.
                    fixture.log("benign_version", version=fixture.metadata["version"])
                elif fixture.scenario == "stale-precheck":
                    fixture.next_version = str(int(fixture.metadata["version"]) - 1)
        result = super().rename(object_id,new_name,expected_version_token=expected_version_token)
        if new_name == "FETCH_BALL_DONE":
            fixture.log("normalized_terminal", outcome=result.outcome.value)
        return result


class ScheduledWalker(StateWalker):
    def walk(self, **kwargs):
        fixture = self.backend.service
        terminal = kwargs["expected_state"] == "RETURNING" and kwargs["target_state"] == "DONE"
        if terminal and fixture.scenario == "foreign-before-fence": fixture.foreign_generation()
        report = super().walk(**kwargs)
        if terminal:
            fixture.log("terminal_report", outcome=report.outcome.value,
                        mutations=report.mutation_attempts, probes=report.confirmation_probes)
        return report


class NoProcessExecutor:
    calls = 0
    def execute(self, body, *, now_epoch_s, cancel_requested=None):
        self.calls += 1
        report = ExecutionReport(ExecutionDisposition.EXITED,0,"synthetic-success","",1.0,2.0)
        return LocalExecution(report, BoundedResult("synthetic-success","",None,None,None,True))


def run_scenario(scenario):
    fixture, clock, executor = ControlledFiles(scenario), Clock(), NoProcessExecutor()
    backend = ScheduledBackend(fixture,media_upload_factory=lambda data, **kw: {"data":data})
    policy = RetryPolicy((0.01,0.02,0.04),3)
    walker = ScheduledWalker(backend,policy,clock.monotonic,clock.sleep)
    keeper = BodyKeeper(backend,policy,clock.monotonic,clock.sleep)
    pipeline = BallPipeline(backend,walker,keeper,executor,clock.epoch)
    try:
        result = pipeline.process_one(OBJECT)
        outcome = result.status.value
    except BallPipelineError:
        outcome = "PUBLICATION_ERROR"
    body = json.loads(fixture.content)
    original = json.loads(fixture.recorded_result) if fixture.recorded_result else None
    check = dict(original or {})
    check["result_sha256"] = None
    valid_result = original is not None and original["result_sha256"] == hashlib.sha256(canonical_json_text(check).encode()).hexdigest()
    return dict(scenario=scenario, scope="SYNTHETIC_ONLY_NO_PROCESS_OR_NETWORK",
                pipeline_outcome=outcome, final_state=fixture.metadata["name"],
                final_generation=body["generation"], body_result=body.get("result_code"),
                recorded_exit_code=None if original is None else original["exit_code"],
                recorded_result_hash_valid=valid_result, original_result_unchanged=fixture.content==fixture.recorded_result,
                execution_calls=executor.calls, terminal_attempts=fixture.terminal_attempts,
                terminal_wire_calls=fixture.terminal_wire_calls, body_writes=fixture.body_writes,
                synthetic_elapsed_s=round(clock.now-100,6), trace=fixture.trace)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=(*SCENARIOS,"all"), default="all")
    args = parser.parse_args(argv)
    scenarios = SCENARIOS if args.scenario == "all" else (args.scenario,)
    print(json.dumps([run_scenario(name) for name in scenarios],sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
