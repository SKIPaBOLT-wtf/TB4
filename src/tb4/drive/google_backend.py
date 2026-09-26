from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from .backend import (
    CreatedObject,
    DriveBackend,
    DriveCapabilities,
    MutationReceipt,
    ObjectMetadata,
    TextObject,
)
from .errors import BackendOutcome, BackendResult


_GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"
_METADATA_FIELDS = "id,name,parents,mimeType,version,size,modifiedTime"


@dataclass(slots=True)
class GoogleDriveBackend:
    """Google Drive v3 adapter for exact-ID TB4 operations.

    IP-48 implements the normal control-path operations only. Maintenance
    creation/move/list/delete methods remain explicit unsupported stubs until
    IP-49 so callers cannot accidentally turn a missing exact operation into a
    hidden directory scan.

    Google Drive exposes a monotonically increasing file version but no
    documented atomic update-if-version REST parameter. expected_version_token
    is therefore a compare-before-mutation guard, not a provider CAS. TB4's
    verified readback, state ownership, and generation fencing remain required.
    """

    service: Any
    media_upload_factory: Callable[..., Any] | None = None
    operation_observer: Callable[[str], None] | None = None
    operation_counts: dict[str, int] = field(default_factory=dict, init=False)

    capabilities = DriveCapabilities(
        stable_object_ids=True,
        exact_metadata_read=True,
        exact_text_read=True,
        atomic_rename_request=True,
        atomic_move_request=True,
        create_text=True,
        change_feed=False,
        maintenance_listing=True,
        permanent_delete=True,
        atomic_version_precondition=False,
    )

    def get_metadata(self, object_id: str) -> BackendResult[ObjectMetadata]:
        self._record_operation("get_metadata")
        try:
            request = self.service.files().get(
                fileId=object_id,
                fields=_METADATA_FIELDS,
                supportsAllDrives=True,
            )
            raw = request.execute()
            return BackendResult.success(self._metadata(raw))
        except Exception as exc:
            return self._normalized_failure(exc, mutation=False)

    def read_text(self, object_id: str) -> BackendResult[TextObject]:
        self._record_operation("read_text")
        metadata = self.get_metadata(object_id)
        if not metadata.ok or metadata.value is None:
            return BackendResult.failure(
                metadata.outcome,
                message=metadata.message,
                provider_code=metadata.provider_code,
                provider_request_id=metadata.provider_request_id,
            )
        if metadata.value.is_folder:
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="folder cannot be read as text",
            )

        try:
            request = self.service.files().get_media(
                fileId=object_id,
                supportsAllDrives=True,
            )
            payload = request.execute()
            if isinstance(payload, str):
                text = payload
            elif isinstance(payload, (bytes, bytearray)):
                try:
                    text = bytes(payload).decode("utf-8")
                except UnicodeDecodeError:
                    return BackendResult.failure(
                        BackendOutcome.CONFLICT,
                        message="Drive object is not UTF-8 text",
                    )
            else:
                return BackendResult.failure(
                    BackendOutcome.CONFLICT,
                    message="Drive media response is not text bytes",
                )
            return BackendResult.success(TextObject(metadata.value, text))
        except Exception as exc:
            return self._normalized_failure(exc, mutation=False)

    def replace_text(
        self,
        object_id: str,
        text: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        self._record_operation("replace_text")
        precondition = self._check_expected_version(object_id, expected_version_token)
        if precondition is not None:
            return precondition

        try:
            media = self._media_upload(text.encode("utf-8"))
            request = self.service.files().update(
                fileId=object_id,
                media_body=media,
                fields=_METADATA_FIELDS,
                supportsAllDrives=True,
            )
            raw = request.execute()
            metadata = self._metadata(raw)
            if metadata.object_id != object_id:
                return BackendResult.failure(
                    BackendOutcome.AMBIGUOUS,
                    message="Drive content update returned a different object ID",
                )
            return BackendResult.success(
                MutationReceipt(
                    object_id=object_id,
                    version_token=metadata.version_token,
                )
            )
        except Exception as exc:
            return self._normalized_failure(exc, mutation=True)

    def rename(
        self,
        object_id: str,
        new_name: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        self._record_operation("rename")
        if not new_name:
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="name must not be empty",
            )
        precondition = self._check_expected_version(object_id, expected_version_token)
        if precondition is not None:
            return precondition

        try:
            request = self.service.files().update(
                fileId=object_id,
                body={"name": new_name},
                fields=_METADATA_FIELDS,
                supportsAllDrives=True,
            )
            raw = request.execute()
            metadata = self._metadata(raw)
            if metadata.object_id != object_id:
                return BackendResult.failure(
                    BackendOutcome.AMBIGUOUS,
                    message="Drive rename returned a different object ID",
                )
            return BackendResult.success(
                MutationReceipt(
                    object_id=object_id,
                    requested_name=new_name,
                    version_token=metadata.version_token,
                )
            )
        except Exception as exc:
            return self._normalized_failure(exc, mutation=True)

    def move(
        self,
        object_id: str,
        new_parent_id: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        self._record_operation("move")
        current = self.get_metadata(object_id)
        if not current.ok or current.value is None:
            return BackendResult.failure(
                current.outcome,
                message=current.message,
                provider_code=current.provider_code,
                provider_request_id=current.provider_request_id,
            )
        if (
            expected_version_token is not None
            and current.value.version_token != expected_version_token
        ):
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="expected Drive version does not match current file version",
            )
        old_parents = current.value.parent_ids
        if not old_parents:
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="Drive object has no removable parent",
            )
        if old_parents == (new_parent_id,):
            return BackendResult.success(
                MutationReceipt(
                    object_id=object_id,
                    requested_parent_id=new_parent_id,
                    version_token=current.value.version_token,
                )
            )

        try:
            request = self.service.files().update(
                fileId=object_id,
                addParents=new_parent_id,
                removeParents=",".join(old_parents),
                fields=_METADATA_FIELDS,
                supportsAllDrives=True,
            )
            raw = request.execute()
            metadata = self._metadata(raw)
            if metadata.object_id != object_id:
                return BackendResult.failure(
                    BackendOutcome.AMBIGUOUS,
                    message="Drive move returned a different object ID",
                )
            return BackendResult.success(
                MutationReceipt(
                    object_id=object_id,
                    requested_parent_id=new_parent_id,
                    version_token=metadata.version_token,
                )
            )
        except Exception as exc:
            return self._normalized_failure(exc, mutation=True)

    def create_folder(
        self,
        parent_id: str,
        name: str,
    ) -> BackendResult[CreatedObject]:
        self._record_operation("create_folder")
        if not name:
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="folder name must not be empty",
            )
        try:
            request = self.service.files().create(
                body={
                    "name": name,
                    "mimeType": _GOOGLE_FOLDER_MIME,
                    "parents": [parent_id],
                },
                fields=_METADATA_FIELDS,
                supportsAllDrives=True,
            )
            raw = request.execute()
            return BackendResult.success(CreatedObject(self._metadata(raw)))
        except Exception as exc:
            failure = self._normalized_failure(exc, mutation=True)
            return BackendResult.failure(
                failure.outcome,
                message=failure.message,
                provider_code=failure.provider_code,
                provider_request_id=failure.provider_request_id,
            )

    def create_text(
        self,
        parent_id: str,
        name: str,
        text: str,
    ) -> BackendResult[CreatedObject]:
        self._record_operation("create_text")
        if not name:
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="text object name must not be empty",
            )
        try:
            media = self._media_upload(text.encode("utf-8"))
            request = self.service.files().create(
                body={
                    "name": name,
                    "mimeType": "text/plain",
                    "parents": [parent_id],
                },
                media_body=media,
                fields=_METADATA_FIELDS,
                supportsAllDrives=True,
            )
            raw = request.execute()
            return BackendResult.success(CreatedObject(self._metadata(raw)))
        except Exception as exc:
            failure = self._normalized_failure(exc, mutation=True)
            return BackendResult.failure(
                failure.outcome,
                message=failure.message,
                provider_code=failure.provider_code,
                provider_request_id=failure.provider_request_id,
            )

    def delete(
        self,
        object_id: str,
        *,
        expected_version_token: str | None = None,
    ) -> BackendResult[MutationReceipt]:
        self._record_operation("delete")
        current = self.get_metadata(object_id)
        if not current.ok or current.value is None:
            return BackendResult.failure(
                current.outcome,
                message=current.message,
                provider_code=current.provider_code,
                provider_request_id=current.provider_request_id,
            )
        if current.value.is_folder:
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="TB4 v1 refuses permanent folder deletion",
            )
        if (
            expected_version_token is not None
            and current.value.version_token != expected_version_token
        ):
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="expected Drive version does not match current file version",
            )
        try:
            request = self.service.files().delete(
                fileId=object_id,
                supportsAllDrives=True,
            )
            request.execute()
            return BackendResult.success(MutationReceipt(object_id=object_id))
        except Exception as exc:
            return self._normalized_failure(exc, mutation=True)

    def list_children(
        self,
        parent_id: str,
    ) -> BackendResult[Sequence[ObjectMetadata]]:
        self._record_operation("list_children")
        query_parent = _drive_query_literal(parent_id)
        page_token: str | None = None
        seen_tokens: set[str] = set()
        children: list[ObjectMetadata] = []

        while True:
            try:
                request = self.service.files().list(
                    q=f"'{query_parent}' in parents and trashed = false",
                    spaces="drive",
                    fields=f"nextPageToken,incompleteSearch,files({_METADATA_FIELDS})",
                    pageSize=1000,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                raw = request.execute()
            except Exception as exc:
                failure = self._normalized_failure(exc, mutation=False)
                return BackendResult.failure(
                    failure.outcome,
                    message=failure.message,
                    provider_code=failure.provider_code,
                    provider_request_id=failure.provider_request_id,
                )

            if raw.get("incompleteSearch"):
                return BackendResult.failure(
                    BackendOutcome.TRANSIENT_ERROR,
                    message="Google Drive returned an incomplete child search",
                )

            for item in raw.get("files", []):
                children.append(self._metadata(item))

            next_token_raw = raw.get("nextPageToken")
            if not next_token_raw:
                break
            next_token = str(next_token_raw)
            if next_token in seen_tokens:
                return BackendResult.failure(
                    BackendOutcome.TRANSIENT_ERROR,
                    message="Google Drive repeated a child-list page token",
                )
            seen_tokens.add(next_token)
            page_token = next_token

        children.sort(key=lambda item: item.object_id)
        return BackendResult.success(tuple(children))

    def _check_expected_version(
        self,
        object_id: str,
        expected_version_token: str | None,
    ) -> BackendResult[MutationReceipt] | None:
        if expected_version_token is None:
            return None
        observed = self.get_metadata(object_id)
        if not observed.ok or observed.value is None:
            return BackendResult.failure(
                observed.outcome,
                message=observed.message,
                provider_code=observed.provider_code,
                provider_request_id=observed.provider_request_id,
            )
        if observed.value.version_token != expected_version_token:
            return BackendResult.failure(
                BackendOutcome.CONFLICT,
                message="expected Drive version does not match current file version",
            )
        return None

    def _record_operation(self, operation: str) -> None:
        self.operation_counts[operation] = self.operation_counts.get(operation, 0) + 1
        if self.operation_observer is not None:
            self.operation_observer(operation)

    def _media_upload(self, data: bytes):
        if self.media_upload_factory is not None:
            return self.media_upload_factory(
                data,
                mimetype="text/plain; charset=utf-8",
                resumable=False,
            )
        try:
            from googleapiclient.http import MediaInMemoryUpload
        except Exception as exc:
            raise RuntimeError(
                f"Google media upload support unavailable: {type(exc).__name__}"
            ) from exc
        return MediaInMemoryUpload(
            data,
            mimetype="text/plain; charset=utf-8",
            resumable=False,
        )

    @staticmethod
    def _metadata(raw: dict[str, Any]) -> ObjectMetadata:
        try:
            object_id = str(raw["id"])
            name = str(raw["name"])
            mime_type = str(raw["mimeType"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Google metadata response is missing required fields") from exc

        parents_raw = raw.get("parents") or []
        parents = tuple(str(value) for value in parents_raw)

        version = raw.get("version")
        size = raw.get("size")
        modified = raw.get("modifiedTime")
        return ObjectMetadata(
            object_id=object_id,
            name=name,
            parent_ids=parents,
            is_folder=mime_type == _GOOGLE_FOLDER_MIME,
            version_token=None if version is None else str(version),
            size_bytes=None if size is None else int(size),
            modified_epoch_s=_parse_google_time(modified),
        )

    @classmethod
    def _normalized_failure(
        cls,
        exc: Exception,
        *,
        mutation: bool,
    ) -> BackendResult:
        status = _http_status(exc)
        reason = _google_reason(exc)
        request_id = _provider_request_id(exc)
        provider_code = _provider_code(status, reason)

        if status == 404:
            outcome = BackendOutcome.NOT_FOUND
            message = "Google Drive object not found"
        elif status in {401, 403} and reason not in {
            "rateLimitExceeded",
            "userRateLimitExceeded",
            "quotaExceeded",
        }:
            outcome = BackendOutcome.PERMISSION_DENIED
            message = "Google Drive permission or authorization denied"
        elif status == 409:
            outcome = BackendOutcome.CONFLICT
            message = "Google Drive reported a conflict"
        elif status == 429 or status in {500, 502, 503, 504} or reason in {
            "rateLimitExceeded",
            "userRateLimitExceeded",
            "quotaExceeded",
            "backendError",
        }:
            outcome = (
                BackendOutcome.AMBIGUOUS
                if mutation and status in {500, 502, 503, 504}
                else BackendOutcome.TRANSIENT_ERROR
            )
            message = (
                "Google Drive mutation outcome is uncertain"
                if outcome is BackendOutcome.AMBIGUOUS
                else "Google Drive request is transiently unavailable"
            )
        elif status is not None:
            outcome = BackendOutcome.AMBIGUOUS if mutation else BackendOutcome.TRANSIENT_ERROR
            message = "Google Drive request failed with a normalized provider error"
        else:
            outcome = BackendOutcome.AMBIGUOUS if mutation else BackendOutcome.TRANSIENT_ERROR
            message = (
                "Google Drive mutation may have been applied"
                if mutation
                else "Google Drive read failed before a trustworthy result"
            )

        return BackendResult.failure(
            outcome,
            message=message,
            provider_code=provider_code,
            provider_request_id=request_id,
        )


def _drive_query_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _parse_google_time(value: Any) -> int | None:
    if value is None:
        return None
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except (ValueError, OverflowError):
        return None


def _http_status(exc: Exception) -> int | None:
    response = getattr(exc, "resp", None)
    status = getattr(response, "status", None)
    try:
        return None if status is None else int(status)
    except (TypeError, ValueError):
        return None


def _google_reason(exc: Exception) -> str | None:
    content = getattr(exc, "content", None)
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if not isinstance(content, str):
        return None
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    errors = payload.get("error", {}).get("errors", [])
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        reason = errors[0].get("reason")
        return str(reason) if reason else None
    return None


def _provider_request_id(exc: Exception) -> str | None:
    response = getattr(exc, "resp", None)
    if response is None:
        return None
    for key in ("x-goog-request-id", "x-guploader-uploadid", "x-request-id"):
        try:
            value = response.get(key)
        except Exception:
            value = None
        if value:
            text = str(value)
            return text[:256]
    return None


def _provider_code(status: int | None, reason: str | None) -> str | None:
    if status is None and reason is None:
        return None
    parts = []
    if status is not None:
        parts.append(f"HTTP_{status}")
    if reason:
        safe = "".join(
            char if char.isalnum() else "_" for char in reason
        ).strip("_").upper()
        if safe:
            parts.append(safe[:96])
    return "_".join(parts) if parts else None
