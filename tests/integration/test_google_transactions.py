from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.retry import RetryPolicy
from tb4.drive.body_keeper import BodyKeeper, BodyWriteOutcome
from tb4.drive.google_backend import GoogleDriveBackend
from tb4.drive.state_walker import StateWalker, StateWalkOutcome


ROOT = Path(__file__).resolve().parents[2]
FETCH_FIXTURE = ROOT / "protocol" / "examples" / "fetch-ball" / "inline-toss.json"


class FakeResponse(dict):
    def __init__(self, status: int, **headers):
        super().__init__(headers)
        self.status = status


class FakeHttpError(Exception):
    def __init__(self, status: int, reason: str | None = None):
        self.resp = FakeResponse(status)
        payload = {"error": {"errors": []}}
        if reason is not None:
            payload["error"]["errors"].append({"reason": reason})
        self.content = json.dumps(payload).encode("utf-8")
        super().__init__(f"fake HTTP {status}")


class FakeRequest:
    def __init__(self, action):
        self.action = action

    def execute(self):
        if isinstance(self.action, Exception):
            raise self.action
        if callable(self.action):
            return self.action()
        return self.action


@dataclass
class FakeClock:
    now: float = 100.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class TransactionFiles:
    metadata: dict
    content: dict[str, bytes]

    def __post_init__(self):
        self.get_calls = 0
        self.get_media_calls = 0
        self.update_calls = 0
        self.list_calls = 0
        self.rename_apply_then_timeout = False
        self.body_apply_then_timeout = False
        self.metadata_transient_reads_after_update = 0
        self.media_stale_reads_after_update = 0
        self._old_media_after_update: bytes | None = None

    def get(self, **kwargs):
        self.get_calls += 1
        if self.metadata_transient_reads_after_update > 0:
            self.metadata_transient_reads_after_update -= 1
            return FakeRequest(FakeHttpError(429, "rateLimitExceeded"))
        return FakeRequest(dict(self.metadata[kwargs["fileId"]]))

    def get_media(self, **kwargs):
        self.get_media_calls += 1
        object_id = kwargs["fileId"]
        if (
            self.media_stale_reads_after_update > 0
            and self._old_media_after_update is not None
        ):
            self.media_stale_reads_after_update -= 1
            return FakeRequest(self._old_media_after_update)
        return FakeRequest(self.content[object_id])

    def update(self, **kwargs):
        self.update_calls += 1
        object_id = kwargs["fileId"]

        def apply():
            current = dict(self.metadata[object_id])
            if "body" in kwargs:
                current.update(kwargs["body"])
            if "media_body" in kwargs:
                previous = self.content[object_id]
                self._old_media_after_update = previous
                self.content[object_id] = kwargs["media_body"]["data"]
                current["size"] = str(len(self.content[object_id]))
            current["version"] = str(int(current["version"]) + 1)
            self.metadata[object_id] = current

            should_timeout = (
                ("body" in kwargs and self.rename_apply_then_timeout)
                or ("media_body" in kwargs and self.body_apply_then_timeout)
            )
            if should_timeout:
                self.rename_apply_then_timeout = False
                self.body_apply_then_timeout = False
                raise TimeoutError("response lost after mutation applied")
            return dict(current)

        return FakeRequest(apply)

    def list(self, **kwargs):
        self.list_calls += 1
        raise AssertionError("normal transaction path must never enumerate folders")


@dataclass
class FakeService:
    resource: TransactionFiles

    def files(self):
        return self.resource


def metadata(name: str, *, version="7"):
    return {
        "id": "file-1",
        "name": name,
        "parents": ["playground-1"],
        "mimeType": "text/plain",
        "version": version,
        "size": "2",
        "modifiedTime": "2026-09-26T12:00:00Z",
    }


def make_backend(name: str, body_text: str):
    files = TransactionFiles(
        metadata={"file-1": metadata(name)},
        content={"file-1": body_text.encode("utf-8")},
    )
    backend = GoogleDriveBackend(
        FakeService(files),
        media_upload_factory=lambda data, **kwargs: {"data": data, **kwargs},
    )
    return backend, files


def policy():
    return RetryPolicy((0.01, 0.02, 0.04, 0.08), 3)


def fetch_body():
    return json.loads(FETCH_FIXTURE.read_text(encoding="utf-8"))


def test_rename_applied_but_response_lost_reconciles_same_id_without_second_write():
    backend, files = make_backend("FETCH_BALL_READY", "{}")
    files.rename_apply_then_timeout = True
    clock = FakeClock()
    walker = StateWalker(backend, policy(), clock.monotonic, clock.sleep)

    report = walker.walk(
        object_id="file-1",
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.NEW_SUCCESS
    assert files.metadata["file-1"]["id"] == "file-1"
    assert files.metadata["file-1"]["name"] == "FETCH_BALL_LOADING"
    assert files.update_calls == 1
    assert files.list_calls == 0


def test_body_write_delayed_media_visibility_retries_reads_not_write():
    old_body = json.dumps(fetch_body(), sort_keys=True, separators=(",", ":")) + "\n"
    backend, files = make_backend("FETCH_BALL_LOADING", old_body)
    files.media_stale_reads_after_update = 2
    clock = FakeClock()
    keeper = BodyKeeper(backend, policy(), clock.monotonic, clock.sleep)

    body = fetch_body()
    body["operation_id"] = "job-google-delay-001"
    body["generation"] = 42

    report = keeper.replace_verified(
        object_id="file-1",
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=body,
    )

    assert report.outcome is BodyWriteOutcome.VERIFIED_SUCCESS
    assert report.confirmation_probes >= 3
    assert files.update_calls == 1
    assert files.list_calls == 0


def test_rate_limit_during_rename_confirmation_is_retried_as_read_visibility():
    backend, files = make_backend("FETCH_BALL_READY", "{}")
    clock = FakeClock()
    walker = StateWalker(backend, policy(), clock.monotonic, clock.sleep)

    # The Google backend pre-reads version immediately before mutation.
    # Queue the transient metadata fault only after update has applied.
    original_update = files.update

    def update_with_post_mutation_rate_limit(**kwargs):
        request = original_update(**kwargs)
        original_action = request.action

        def wrapped():
            result = original_action()
            files.metadata_transient_reads_after_update = 1
            return result

        return FakeRequest(wrapped)

    files.update = update_with_post_mutation_rate_limit

    report = walker.walk(
        object_id="file-1",
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.NEW_SUCCESS
    assert report.confirmation_probes >= 2
    assert files.update_calls == 1
    assert files.list_calls == 0


def test_body_mutation_applied_but_response_lost_is_hash_reconciled_without_rewrite():
    backend, files = make_backend("FETCH_BALL_LOADING", "{}")
    files.body_apply_then_timeout = True
    clock = FakeClock()
    keeper = BodyKeeper(backend, policy(), clock.monotonic, clock.sleep)

    body = fetch_body()
    body["operation_id"] = "job-google-ambiguous-body"
    body["generation"] = 43

    report = keeper.replace_verified(
        object_id="file-1",
        logical_object=LogicalObject.FETCH_BALL,
        state="LOADING",
        actor=Role.COACH,
        schema_name="fetch-ball.schema.json",
        body=body,
    )

    assert report.outcome is BodyWriteOutcome.VERIFIED_SUCCESS
    assert files.update_calls == 1
    assert files.metadata["file-1"]["id"] == "file-1"
    assert files.list_calls == 0


def test_persistent_google_read_delay_returns_unconfirmed_without_second_mutation():
    backend, files = make_backend("FETCH_BALL_READY", "{}")
    clock = FakeClock()
    walker = StateWalker(
        backend,
        RetryPolicy((0.01, 0.02), 2),
        clock.monotonic,
        clock.sleep,
    )

    original_update = files.update

    def update_with_long_visibility_delay(**kwargs):
        request = original_update(**kwargs)
        original_action = request.action

        def wrapped():
            result = original_action()
            # Every confirmation metadata read in this bounded budget is
            # transient; helper must stop without issuing another update.
            files.metadata_transient_reads_after_update = 100
            return result

        return FakeRequest(wrapped)

    files.update = update_with_long_visibility_delay

    report = walker.walk(
        object_id="file-1",
        logical_object=LogicalObject.FETCH_BALL,
        expected_state="READY",
        target_state="LOADING",
        actor=Role.COACH,
    )

    assert report.outcome is StateWalkOutcome.UNCONFIRMED
    assert files.update_calls == 1
    assert files.list_calls == 0
