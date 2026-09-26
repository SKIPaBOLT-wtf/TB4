from __future__ import annotations

import json
from dataclasses import dataclass

from tb4.drive.errors import BackendOutcome
from tb4.drive.google_backend import GoogleDriveBackend


class FakeResponse(dict):
    def __init__(self, status: int, **headers):
        super().__init__(headers)
        self.status = status


class FakeHttpError(Exception):
    def __init__(self, status: int, reason: str | None = None, request_id: str | None = None):
        headers = {}
        if request_id:
            headers["x-goog-request-id"] = request_id
        self.resp = FakeResponse(status, **headers)
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
class FakeFiles:
    metadata: dict[str, dict]
    content: dict[str, bytes]

    def __post_init__(self):
        self.get_calls = []
        self.media_calls = []
        self.update_calls = []
        self.list_calls = []
        self.next_get_error = None
        self.next_media_error = None
        self.next_update_error = None

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        if self.next_get_error is not None:
            error = self.next_get_error
            self.next_get_error = None
            return FakeRequest(error)

        object_id = kwargs["fileId"]
        if object_id not in self.metadata:
            return FakeRequest(FakeHttpError(404))
        return FakeRequest(dict(self.metadata[object_id]))

    def get_media(self, **kwargs):
        self.media_calls.append(kwargs)
        if self.next_media_error is not None:
            error = self.next_media_error
            self.next_media_error = None
            return FakeRequest(error)
        object_id = kwargs["fileId"]
        if object_id not in self.content:
            return FakeRequest(FakeHttpError(404))
        return FakeRequest(self.content[object_id])

    def update(self, **kwargs):
        self.update_calls.append(kwargs)
        if self.next_update_error is not None:
            error = self.next_update_error
            self.next_update_error = None
            return FakeRequest(error)

        object_id = kwargs["fileId"]

        def apply():
            current = dict(self.metadata[object_id])
            if "body" in kwargs:
                current.update(kwargs["body"])
            if "media_body" in kwargs:
                self.content[object_id] = kwargs["media_body"]["data"]
                current["size"] = str(len(self.content[object_id]))
            current["version"] = str(int(current.get("version", "0")) + 1)
            self.metadata[object_id] = current
            return dict(current)

        return FakeRequest(apply)

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        raise AssertionError("normal exact-object tests must never list folders")


@dataclass
class FakeService:
    files_resource: FakeFiles

    def files(self):
        return self.files_resource


def base_metadata(object_id="file-1", *, name="FETCH_BALL_READY", version="7"):
    return {
        "id": object_id,
        "name": name,
        "parents": ["playground-1"],
        "mimeType": "text/plain",
        "version": version,
        "size": "5",
        "modifiedTime": "2026-09-26T12:34:56Z",
    }


def make_backend():
    files = FakeFiles(
        metadata={"file-1": base_metadata()},
        content={"file-1": b"hello"},
    )
    backend = GoogleDriveBackend(
        FakeService(files),
        media_upload_factory=lambda data, **kwargs: {
            "data": data,
            **kwargs,
        },
    )
    return backend, files


def test_metadata_is_read_by_exact_file_id_and_normalized():
    backend, files = make_backend()

    result = backend.get_metadata("file-1")

    assert result.ok and result.value is not None
    assert result.value.object_id == "file-1"
    assert result.value.name == "FETCH_BALL_READY"
    assert result.value.parent_ids == ("playground-1",)
    assert result.value.version_token == "7"
    assert result.value.size_bytes == 5
    assert result.value.modified_epoch_s is not None
    assert files.get_calls == [
        {
            "fileId": "file-1",
            "fields": "id,name,parents,mimeType,version,size,modifiedTime",
            "supportsAllDrives": True,
        }
    ]
    assert files.list_calls == []


def test_read_text_uses_exact_metadata_and_media_calls_without_listing():
    backend, files = make_backend()

    result = backend.read_text("file-1")

    assert result.ok and result.value is not None
    assert result.value.text == "hello"
    assert result.value.metadata.object_id == "file-1"
    assert files.media_calls == [{"fileId": "file-1", "supportsAllDrives": True}]
    assert files.list_calls == []


def test_replace_text_preserves_id_and_returns_new_version():
    backend, files = make_backend()

    result = backend.replace_text(
        "file-1",
        "new body",
        expected_version_token="7",
    )

    assert result.ok and result.value is not None
    assert result.value.object_id == "file-1"
    assert result.value.version_token == "8"
    assert files.content["file-1"] == b"new body"
    assert files.metadata["file-1"]["id"] == "file-1"
    assert files.list_calls == []


def test_replace_text_rejects_stale_pre_read_version_without_mutation():
    backend, files = make_backend()

    result = backend.replace_text(
        "file-1",
        "must not write",
        expected_version_token="6",
    )

    assert result.outcome is BackendOutcome.CONFLICT
    assert files.content["file-1"] == b"hello"
    assert files.update_calls == []


def test_rename_is_single_same_id_update():
    backend, files = make_backend()

    result = backend.rename(
        "file-1",
        "FETCH_BALL_LOADING",
        expected_version_token="7",
    )

    assert result.ok and result.value is not None
    assert result.value.object_id == "file-1"
    assert result.value.requested_name == "FETCH_BALL_LOADING"
    assert files.metadata["file-1"]["name"] == "FETCH_BALL_LOADING"
    assert len(files.update_calls) == 1
    assert files.update_calls[0]["fileId"] == "file-1"
    assert files.list_calls == []


def test_404_is_normalized_as_not_found():
    backend, _ = make_backend()

    result = backend.get_metadata("missing")

    assert result.outcome is BackendOutcome.NOT_FOUND
    assert result.provider_code == "HTTP_404"


def test_permission_denied_is_normalized_without_provider_error_text():
    backend, files = make_backend()
    files.next_get_error = FakeHttpError(
        403,
        "insufficientFilePermissions",
        request_id="req-403",
    )

    result = backend.get_metadata("file-1")

    assert result.outcome is BackendOutcome.PERMISSION_DENIED
    assert result.provider_request_id == "req-403"
    assert result.provider_code == "HTTP_403_INSUFFICIENTFILEPERMISSIONS"


def test_rate_limit_is_normalized_as_transient():
    backend, files = make_backend()
    files.next_get_error = FakeHttpError(403, "rateLimitExceeded")

    result = backend.get_metadata("file-1")

    assert result.outcome is BackendOutcome.TRANSIENT_ERROR
    assert "RATELIMITEXCEEDED" in (result.provider_code or "")


def test_429_is_transient_for_read():
    backend, files = make_backend()
    files.next_get_error = FakeHttpError(429, "rateLimitExceeded")

    result = backend.get_metadata("file-1")

    assert result.outcome is BackendOutcome.TRANSIENT_ERROR


def test_timeout_after_mutation_request_is_ambiguous_not_blind_failure():
    backend, files = make_backend()
    files.next_update_error = TimeoutError("fake timeout")

    result = backend.rename(
        "file-1",
        "FETCH_BALL_LOADING",
        expected_version_token="7",
    )

    assert result.outcome is BackendOutcome.AMBIGUOUS
    assert "timeout" not in (result.message or "").lower()


def test_server_error_during_mutation_is_ambiguous():
    backend, files = make_backend()
    files.next_update_error = FakeHttpError(503, "backendError")

    result = backend.replace_text(
        "file-1",
        "maybe applied",
        expected_version_token="7",
    )

    assert result.outcome is BackendOutcome.AMBIGUOUS


def test_invalid_utf8_is_conflict_not_crash():
    backend, files = make_backend()
    files.content["file-1"] = b"\xff\xfe"

    result = backend.read_text("file-1")

    assert result.outcome is BackendOutcome.CONFLICT


def test_ip48_does_not_smuggle_maintenance_listing_into_normal_operations():
    backend, files = make_backend()

    assert backend.capabilities.maintenance_listing is True
    assert backend.capabilities.atomic_version_precondition is False
    assert files.list_calls == []
