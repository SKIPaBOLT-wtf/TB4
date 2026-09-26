from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.state_walker import StateWalker
from tb4.fetcher.artifact_runner import ArtifactRunner
from tb4.fetcher.artifact_spool import ArtifactSpool
from tb4.fetcher.ball_pipeline import (
    BallPipeline,
    BallPipelineStatus,
    LocalExecution,
    LocalJobExecutor,
)
from tb4.fetcher.cancellation import StopBallCancellation
from tb4.fetcher.heartbeat import HeartbeatPublisher
from tb4.fetcher.idle_manager import IdleDecision, IdleManager
from tb4.fetcher.service import FetcherServiceLifecycle
from tb4.fetcher.subprocess_runner import SubprocessRunner
from tb4.runtime_support import (
    RuntimeConfigurationError,
    RuntimeContext,
    build_context,
    optional_bool,
    require_string,
    require_table,
)


@dataclass(slots=True)
class _HeartbeatExecutor:
    inner: LocalJobExecutor
    heartbeat: HeartbeatPublisher
    stop_event: threading.Event
    tick_s: float = 1.0

    def execute(
        self,
        body,
        *,
        now_epoch_s: int,
        cancel_requested=None,
    ) -> LocalExecution:
        operation_id = str(body["operation_id"])
        generation = int(body["generation"])
        finished = threading.Event()

        def pulse_loop() -> None:
            while not finished.is_set() and not self.stop_event.is_set():
                self.heartbeat.tick(
                    active=True,
                    claimed_generation=generation,
                    claimed_operation_id=operation_id,
                )
                finished.wait(self.tick_s)

        thread = threading.Thread(
            target=pulse_loop,
            name="tb4-fetcher-heartbeat",
            daemon=True,
        )
        thread.start()
        try:
            return self.inner.execute(
                body,
                now_epoch_s=now_epoch_s,
                cancel_requested=cancel_requested,
            )
        finally:
            finished.set()
            thread.join(timeout=max(2.0, self.tick_s * 2))


@dataclass(slots=True)
class FetcherRuntime:
    context: RuntimeContext
    device_id: str
    ephemeral: bool
    lifecycle: FetcherServiceLifecycle
    heartbeat: HeartbeatPublisher
    pipeline: BallPipeline
    state_walker: StateWalker
    body_keeper: BodyKeeper
    fetch_ball_id: str
    stop_ball_id: str
    poll_interval_s: float = 1.0
    _child_active: bool = False
    _cancellation_active: bool = False

    def run(self, stop_event: threading.Event) -> int:
        # The executor needs the same process stop event used by ServiceHost.
        if isinstance(self.pipeline.executor, _HeartbeatExecutor):
            self.pipeline.executor.stop_event = stop_event

        startup = self.lifecycle.startup_inspect()
        if startup.disposition.value == "INVALID":
            raise RuntimeError(startup.message or "FETCHER startup state is invalid")

        while not stop_event.is_set():
            metadata = self.context.backend.get_metadata(self.fetch_ball_id)
            if not metadata.ok or metadata.value is None:
                raise RuntimeError(
                    f"FETCH_BALL metadata unavailable: {metadata.outcome.value}"
                )
            name = metadata.value.name

            active = name in {"FETCH_BALL_CHEW", "FETCH_BALL_RETURNING"}
            self.heartbeat.tick(active=active)

            if name == "FETCH_BALL_TOSS":
                self._process_toss(stop_event)
                continue

            decision = self.lifecycle.tick_idle().idle_decision
            if (
                self.ephemeral
                and decision is IdleDecision.EXIT_IDLE
            ):
                return 0

            stop_event.wait(self.poll_interval_s)

        return 0

    def _process_toss(self, stop_event: threading.Event) -> None:
        remote = self.context.backend.read_text(self.fetch_ball_id)
        if not remote.ok or remote.value is None:
            raise RuntimeError("FETCH_BALL TOSS body is unreadable")
        try:
            body = json.loads(remote.value.text)
            job_id = str(body["operation_id"])
            generation = int(body["generation"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("FETCH_BALL TOSS body has invalid job identity") from exc

        cancellation = StopBallCancellation(
            backend=self.context.backend,
            state_walker=self.state_walker,
            body_keeper=self.body_keeper,
            stop_ball_object_id=self.stop_ball_id,
            fetch_ball_object_id=self.fetch_ball_id,
            job_id=job_id,
            generation=generation,
            monotonic_now=time.monotonic,
            epoch_now=lambda: int(time.time()),
        )

        self._child_active = True
        self._cancellation_active = True
        try:
            result = self.pipeline.process_one(
                self.fetch_ball_id,
                cancel_requested=cancellation.should_cancel,
            )
        finally:
            self._child_active = False
            self._cancellation_active = False

        if result.status is BallPipelineStatus.EXPIRED:
            # Expiry is intentionally not converted into fabricated execution
            # evidence. COACH/WATCHDOG recovery owns stale TOSS handling.
            stop_event.wait(self.poll_interval_s)


def create_runtime_from_context(context: RuntimeContext) -> FetcherRuntime:
    config = context.config
    identity = require_table(config, "identity")
    service = require_table(config, "service")
    execution = require_table(config, "execution")
    device_id = require_string(identity, "device_id")

    if device_id not in context.park_map.devices:
        raise RuntimeConfigurationError(
            "configured FETCHER device_id is not registered in PARK_MAP"
        )

    defaults = context.defaults
    fetch_defaults = defaults["fetcher"]
    job_defaults = defaults["job"]
    retention_defaults = defaults["retention"]

    fetch_ball_id = context.park_map.lookup_device(
        device_id,
        "PLAYGROUND.FETCH_BALL",
    )
    stop_ball_id = context.park_map.lookup_device(
        device_id,
        "PLAYGROUND.STOP_BALL",
    )
    dog_pulse_id = context.park_map.lookup_device(device_id, "DOG_PULSE")
    toy_box_id = context.park_map.lookup_device(device_id, "TOY_BOX")

    artifact_root = Path(require_string(execution, "artifact_work_dir")).expanduser()
    artifact_root.mkdir(parents=True, exist_ok=True)

    walker = StateWalker(
        context.backend,
        context.retry_policy,
        time.monotonic,
        time.sleep,
    )
    keeper = BodyKeeper(
        context.backend,
        context.retry_policy,
        time.monotonic,
        time.sleep,
    )
    heartbeat = HeartbeatPublisher(
        backend=context.backend,
        dog_pulse_object_id=dog_pulse_id,
        device_id=device_id,
        instance_id=f"fetcher-{uuid.uuid4().hex}",
        idle_interval_s=float(fetch_defaults["idle_heartbeat_s"]),
        active_interval_s=float(fetch_defaults["busy_heartbeat_s"]),
        retry_policy=context.retry_policy,
        monotonic_now=time.monotonic,
        epoch_now=lambda: int(time.time()),
        sleeper=time.sleep,
    )

    process_runner = SubprocessRunner()
    artifact_runner = ArtifactRunner(
        temp_root=artifact_root / "scripts",
        process_runner=process_runner,
    )
    artifact_spool = ArtifactSpool(
        backend=context.backend,
        toy_box_folder_id=toy_box_id,
        temp_root=artifact_root / "output",
        inline_result_max_bytes=int(job_defaults["inline_result_max_bytes"]),
        result_tail_max_chars=int(job_defaults["result_tail_max_chars"]),
    )
    local_executor = LocalJobExecutor(
        backend=context.backend,
        process_runner=process_runner,
        artifact_runner=artifact_runner,
        artifact_spool=artifact_spool,
        result_retention_s=int(retention_defaults["toy_box_days"]) * 86400,
    )
    heartbeat_executor = _HeartbeatExecutor(
        local_executor,
        heartbeat,
        threading.Event(),
    )
    pipeline = BallPipeline(
        backend=context.backend,
        state_walker=walker,
        body_keeper=keeper,
        executor=heartbeat_executor,
        epoch_now=lambda: int(time.time()),
    )

    runtime_placeholder: dict[str, FetcherRuntime] = {}
    idle = IdleManager(
        idle_exit_s=float(service.get("idle_exit_s", fetch_defaults["idle_exit_s"])),
        monotonic_now=time.monotonic,
    )
    lifecycle = FetcherServiceLifecycle(
        backend=context.backend,
        fetch_ball_object_id=fetch_ball_id,
        stop_ball_object_id=stop_ball_id,
        heartbeat=heartbeat,
        idle_manager=idle,
        child_active=lambda: runtime_placeholder["runtime"]._child_active,
        cancellation_active=lambda: runtime_placeholder["runtime"]._cancellation_active,
    )

    runtime = FetcherRuntime(
        context=context,
        device_id=device_id,
        ephemeral=optional_bool(service, "ephemeral", True),
        lifecycle=lifecycle,
        heartbeat=heartbeat,
        pipeline=pipeline,
        state_walker=walker,
        body_keeper=keeper,
        fetch_ball_id=fetch_ball_id,
        stop_ball_id=stop_ball_id,
        poll_interval_s=float(service.get("poll_interval_s", 1.0)),
    )
    if runtime.poll_interval_s <= 0:
        raise RuntimeConfigurationError("service.poll_interval_s must be positive")
    runtime_placeholder["runtime"] = runtime
    return runtime


def create_runtime(config_path: Path):
    return create_runtime_from_context(build_context(config_path))
