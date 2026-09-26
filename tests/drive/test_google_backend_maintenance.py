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


def meta(object_id, name, parent, *, folder=False, version=1, size=0):
    return {
        "id": object_id,
        "name": name,
        "parents": [parent],
        "mimeType": (
            "application/vnd.google-apps.folder" if folder else "text/plain"
        ),
        "version": str(version),
        "size": None if folder else str(size),
        "modifiedTime": "2026-09-26T12:00:00Z",
    }


@dataclass
class MaintenanceFiles:
    metadata: dict[str, dict]
    content: dict[str, bytes]

    def __post_init__(self):
        self.create_calls = []
        self.update_calls = []
        self.list_calls = []
        self.delete_calls = []
        self.get_calls = []
        self.next_list_error = None
        self.next_update_error = None
        self.id_counter = 100
        self.pages = None

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        object_id = kwargs["fileId"]
        if object_id not in self.metadata:
            return FakeRequest(FakeHttpError(404))
        return FakeRequest(dict(self.metadata[object_id]))

    def get_media(self, **kwargs):
        object_id = kwargs["fileId"]
        return FakeRequest(self.content[object_id])

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        self.id_counter += 1
        object_id = f"g-{self.id_counter}"
        body = kwargs["body"]
        is_folder = body.get("mimeType") == "application/vnd.google-apps.folder"

        def apply():
            raw = meta(
                object_id,
                body["name"],
                body["parents"][0],
                folder=is_folder,
                version=1,
                size=0,
            )
            self.metadata[object_id] = raw
            if not is_folder and "media_body" in kwargs:
                self.content[object_id] = kwargs["media_body"]["data"]
                raw["size"] = str(len(self.content[object_id]))
            return dict(raw)

        return FakeRequest(apply)

    def update(self, **kwargs):
        self.update_calls.append(kwargs)
        if self.next_update_error is not None:
            error = self.next_update_error
            self.next_update_error = None
            return FakeRequest(error)

        object_id = kwargs["fileId"]

        def apply():
            raw = dict(self.metadata[object_id])
            if kwargs.get("addParents"):
                raw["parents"] = [kwargs["addParents"]]
            if "body" in kwargs:
                raw.update(kwargs["body"])
            raw["version"] = str(int(raw["version"]) + 1)
            self.metadata[object_id] = raw
            return dict(raw)

        return FakeRequest(apply)

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        if self.next_list_error is not None:
            error = self.next_list_error
            self.next_list_error = None
            return FakeRequest(error)
        if self.pages is not None:
            index = 0
            token = kwargs.get("pageToken")
            if token:
                index = int(token.split("-")[-1])
            return FakeRequest(self.pages[index])

        parent = kwargs["q"].split("'")[1]
        files = [
            dict(raw)
            for raw in self.metadata.values()
            if raw.get("parents") == [parent]
        ]
        return FakeRequest({"files": files})

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)
        object_id = kwargs["fileId"]

        def apply():
            self.metadata.pop(object_id, None)
            self.content.pop(object_id, None)
            return {}

        return FakeRequest(apply)


@dataclass
class FakeService:
    resource: MaintenanceFiles

    def files(self):
        return self.resource


def make_backend(observer=None):
    metadata = {
        "old-parent": meta("old-parent", "OLD", "root", folder=True),
        "new-parent": meta("new-parent", "NEW", "root", folder=True),
        "file-1": meta("file-1", "item", "old-parent", version=4, size=3),
    }
    files = MaintenanceFiles(metadata, {"file-1": b"abc"})
    backend = GoogleDriveBackend(
        FakeService(files),
        media_upload_factory=lambda data, **kwargs: {"data": data, **kwargs},
        operation_observer=observer,
    )
    return backend, files


def test_create_folder_uses_exact_parent_and_returns_stable_id():
    backend, files = make_backend()

    result = backend.create_folder("new-parent", "BONEYARD")

    assert result.ok and result.value is not None
    object_id = result.value.metadata.object_id
    assert files.metadata[object_id]["parents"] == ["new-parent"]
    assert files.metadata[object_id]["name"] == "BONEYARD"
    assert result.value.metadata.is_folder is True


def test_create_text_uploads_small_utf8_body_under_exact_parent():
    backend, files = make_backend()

    result = backend.create_text("new-parent", "DOG_TAG", "hello")

    assert result.ok and result.value is not None
    object_id = result.value.metadata.object_id
    assert files.content[object_id] == b"hello"
    call = files.create_calls[-1]
    assert call["body"]["parents"] == ["new-parent"]
    assert call["supportsAllDrives"] is True


def test_move_preserves_object_id_and_replaces_old_parent():
    backend, files = make_backend()

    result = backend.move(
        "file-1",
        "new-parent",
        expected_version_token="4",
    )

    assert result.ok and result.value is not None
    assert result.value.object_id == "file-1"
    assert result.value.requested_parent_id == "new-parent"
    assert files.metadata["file-1"]["parents"] == ["new-parent"]
    call = files.update_calls[-1]
    assert call["addParents"] == "new-parent"
    assert call["removeParents"] == "old-parent"


def test_move_permission_error_is_normalized():
    backend, files = make_backend()
    files.next_update_error = FakeHttpError(403, "insufficientFilePermissions")

    result = backend.move("file-1", "new-parent", expected_version_token="4")

    assert result.outcome is BackendOutcome.PERMISSION_DENIED


def test_list_children_follows_every_page_and_keeps_duplicate_names_distinct():
    backend, files = make_backend()
    first = meta("dup-1", "SAME_NAME", "new-parent", version=1)
    second = meta("dup-2", "SAME_NAME", "new-parent", version=1)
    third = meta("other", "OTHER", "new-parent", version=1)
    files.pages = [
        {
            "files": [first, second],
            "nextPageToken": "page-1",
            "incompleteSearch": False,
        },
        {
            "files": [third],
            "incompleteSearch": False,
        },
    ]

    result = backend.list_children("new-parent")

    assert result.ok and result.value is not None
    assert {item.object_id for item in result.value} == {"dup-1", "dup-2", "other"}
    assert [item.name for item in result.value].count("SAME_NAME") == 2
    assert len(files.list_calls) == 2
    assert files.list_calls[0]["pageSize"] == 1000
    assert files.list_calls[0]["includeItemsFromAllDrives"] is True
    assert "trashed = false" in files.list_calls[0]["q"]


def test_incomplete_search_is_rejected_instead_of_returning_partial_children():
    backend, files = make_backend()
    files.pages = [
        {
            "files": [meta("partial", "PARTIAL", "new-parent")],
            "incompleteSearch": True,
        }
    ]

    result = backend.list_children("new-parent")

    assert result.outcome is BackendOutcome.TRANSIENT_ERROR
    assert result.value is None


def test_list_rate_limit_is_normalized():
    backend, files = make_backend()
    files.next_list_error = FakeHttpError(429, "rateLimitExceeded")

    result = backend.list_children("new-parent")

    assert result.outcome is BackendOutcome.TRANSIENT_ERROR


def test_permanent_delete_removes_file_but_refuses_folder():
    backend, files = make_backend()

    deleted = backend.delete("file-1", expected_version_token="4")
    refused = backend.delete("new-parent")

    assert deleted.ok
    assert "file-1" not in files.metadata
    assert refused.outcome is BackendOutcome.CONFLICT
    assert files.delete_calls == [{"fileId": "file-1", "supportsAllDrives": True}]


def test_delete_stale_version_is_conflict_without_delete_request():
    backend, files = make_backend()

    result = backend.delete("file-1", expected_version_token="3")

    assert result.outcome is BackendOutcome.CONFLICT
    assert files.delete_calls == []


def test_operation_counters_and_observer_cover_maintenance_calls():
    observed = []
    backend, _ = make_backend(observed.append)

    backend.create_folder("new-parent", "A")
    backend.create_text("new-parent", "B", "x")
    backend.list_children("new-parent")
    backend.move("file-1", "new-parent", expected_version_token="4")

    assert backend.operation_counts["create_folder"] == 1
    assert backend.operation_counts["create_text"] == 1
    assert backend.operation_counts["list_children"] == 1
    assert backend.operation_counts["move"] == 1
    assert {"create_folder", "create_text", "list_children", "move"} <= set(observed)


def test_parent_query_literal_is_escaped_not_interpreted_as_extra_query():
    backend, files = make_backend()

    backend.list_children("parent'with\\quote")

    q = files.list_calls[0]["q"]
    assert q.startswith("'parent\\'with\\\\quote' in parents")
