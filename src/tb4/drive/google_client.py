from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Mapping


GOOGLE_DRIVE_CONTROL_SCOPE = "https://www.googleapis.com/auth/drive"


class GoogleAuthOutcome(StrEnum):
    READY = "READY"
    MISSING_LOCAL_CREDENTIALS = "MISSING_LOCAL_CREDENTIALS"
    INVALID_LOCAL_CREDENTIALS = "INVALID_LOCAL_CREDENTIALS"
    REFRESH_FAILED = "REFRESH_FAILED"
    INTERACTIVE_REQUIRED = "INTERACTIVE_REQUIRED"
    INTERACTIVE_FAILED = "INTERACTIVE_FAILED"
    CLIENT_BUILD_FAILED = "CLIENT_BUILD_FAILED"
    UNSUPPORTED_SCOPE = "UNSUPPORTED_SCOPE"


@dataclass(frozen=True, slots=True)
class GoogleAuthConfig:
    """Local-only Google OAuth paths.

    The values are paths, never credential contents. Public repository defaults
    intentionally contain neither paths nor Drive root IDs.
    """

    client_secrets_path: Path
    token_path: Path
    allow_interactive: bool = False
    open_browser: bool = True
    scopes: tuple[str, ...] = (GOOGLE_DRIVE_CONTROL_SCOPE,)

    def __post_init__(self) -> None:
        object.__setattr__(self, "client_secrets_path", Path(self.client_secrets_path).expanduser())
        object.__setattr__(self, "token_path", Path(self.token_path).expanduser())
        normalized = tuple(dict.fromkeys(scope.strip() for scope in self.scopes if scope.strip()))
        object.__setattr__(self, "scopes", normalized)

    @classmethod
    def from_environment(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        allow_interactive: bool = False,
        open_browser: bool = True,
    ) -> "GoogleAuthConfig":
        source = os.environ if env is None else env
        client_path = source.get("TB4_GOOGLE_CLIENT_SECRETS")
        token_path = source.get("TB4_GOOGLE_TOKEN")
        if not client_path or not token_path:
            raise ValueError(
                "TB4_GOOGLE_CLIENT_SECRETS and TB4_GOOGLE_TOKEN must point to local private files"
            )
        return cls(
            Path(client_path),
            Path(token_path),
            allow_interactive=allow_interactive,
            open_browser=open_browser,
        )


@dataclass(frozen=True, slots=True)
class GoogleClientReport:
    outcome: GoogleAuthOutcome
    service: Any | None = None
    message: str | None = None
    token_written: bool = False

    @property
    def ready(self) -> bool:
        return self.outcome is GoogleAuthOutcome.READY and self.service is not None


CredentialsFactory = Any
RequestFactory = Callable[[], Any]
FlowFactory = Any
ServiceBuilder = Callable[..., Any]


def validate_google_scopes(scopes: tuple[str, ...]) -> GoogleClientReport | None:
    """Protocol v1 requires cross-client access to one shared TB4 tree.

    drive.file is intentionally insufficient as the default because TB4 objects
    may be created by another authorized client (for example the AI-side Drive
    connector). Per-file authorization would make visibility depend on which
    client created or explicitly selected each object.
    """

    if GOOGLE_DRIVE_CONTROL_SCOPE not in scopes:
        return GoogleClientReport(
            GoogleAuthOutcome.UNSUPPORTED_SCOPE,
            message=(
                "TB4 protocol v1 requires the full Drive scope for a shared "
                "multi-client control tree"
            ),
        )
    return None


def build_google_drive_client(
    config: GoogleAuthConfig,
    *,
    credentials_cls: CredentialsFactory | None = None,
    request_factory: RequestFactory | None = None,
    flow_cls: FlowFactory | None = None,
    service_builder: ServiceBuilder | None = None,
) -> GoogleClientReport:
    scope_error = validate_google_scopes(config.scopes)
    if scope_error is not None:
        return scope_error

    try:
        if credentials_cls is None:
            from google.oauth2.credentials import Credentials

            credentials_cls = Credentials
        if request_factory is None:
            from google.auth.transport.requests import Request

            request_factory = Request
        if flow_cls is None:
            from google_auth_oauthlib.flow import InstalledAppFlow

            flow_cls = InstalledAppFlow
        if service_builder is None:
            from googleapiclient.discovery import build

            service_builder = build
    except Exception as exc:
        return GoogleClientReport(
            GoogleAuthOutcome.CLIENT_BUILD_FAILED,
            message=f"Google client libraries unavailable: {type(exc).__name__}",
        )

    credentials = None
    token_written = False

    if config.token_path.exists():
        try:
            credentials = credentials_cls.from_authorized_user_file(
                str(config.token_path),
                list(config.scopes),
            )
        except Exception as exc:
            return GoogleClientReport(
                GoogleAuthOutcome.INVALID_LOCAL_CREDENTIALS,
                message=f"local OAuth token could not be loaded: {type(exc).__name__}",
            )

    if credentials is not None and getattr(credentials, "valid", False):
        pass
    elif (
        credentials is not None
        and getattr(credentials, "expired", False)
        and getattr(credentials, "refresh_token", None)
    ):
        try:
            credentials.refresh(request_factory())
            _write_private_token(config.token_path, credentials.to_json())
            token_written = True
        except Exception as exc:
            return GoogleClientReport(
                GoogleAuthOutcome.REFRESH_FAILED,
                message=f"OAuth token refresh failed: {type(exc).__name__}",
            )
    else:
        if not config.allow_interactive:
            if credentials is None and not config.client_secrets_path.exists():
                return GoogleClientReport(
                    GoogleAuthOutcome.MISSING_LOCAL_CREDENTIALS,
                    message="local OAuth client-secrets file is missing",
                )
            return GoogleClientReport(
                GoogleAuthOutcome.INTERACTIVE_REQUIRED,
                message="interactive OAuth authorization is required",
            )

        if not config.client_secrets_path.exists():
            return GoogleClientReport(
                GoogleAuthOutcome.MISSING_LOCAL_CREDENTIALS,
                message="local OAuth client-secrets file is missing",
            )

        try:
            flow = flow_cls.from_client_secrets_file(
                str(config.client_secrets_path),
                list(config.scopes),
            )
            credentials = flow.run_local_server(
                port=0,
                open_browser=config.open_browser,
            )
            _write_private_token(config.token_path, credentials.to_json())
            token_written = True
        except Exception as exc:
            return GoogleClientReport(
                GoogleAuthOutcome.INTERACTIVE_FAILED,
                message=f"interactive OAuth authorization failed: {type(exc).__name__}",
            )

    if credentials is None or not getattr(credentials, "valid", False):
        return GoogleClientReport(
            GoogleAuthOutcome.INVALID_LOCAL_CREDENTIALS,
            message="OAuth credentials are not valid after authorization handling",
        )

    try:
        service = service_builder(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )
    except Exception as exc:
        return GoogleClientReport(
            GoogleAuthOutcome.CLIENT_BUILD_FAILED,
            message=f"Drive API client construction failed: {type(exc).__name__}",
            token_written=token_written,
        )

    return GoogleClientReport(
        GoogleAuthOutcome.READY,
        service=service,
        message="Drive API client ready",
        token_written=token_written,
    )


def _write_private_token(path: Path, text: str) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        # Windows and some filesystems do not implement POSIX mode semantics.
        pass
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
