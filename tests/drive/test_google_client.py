from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tb4.drive.google_client import (
    GOOGLE_DRIVE_CONTROL_SCOPE,
    GoogleAuthConfig,
    GoogleAuthOutcome,
    build_google_drive_client,
)


@dataclass
class FakeCredentials:
    valid: bool = True
    expired: bool = False
    refresh_token: str | None = None
    serialized: str = '{"token":"fake-test-token"}'
    refresh_should_fail: bool = False

    loaded: "FakeCredentials | None" = None

    @classmethod
    def from_authorized_user_file(cls, path, scopes):
        if cls.loaded is None:
            raise ValueError("fake token rejected")
        return cls.loaded

    def refresh(self, request):
        if self.refresh_should_fail:
            raise RuntimeError("fake refresh failed")
        self.valid = True
        self.expired = False

    def to_json(self):
        return self.serialized


class FakeFlow:
    credentials = FakeCredentials()

    @classmethod
    def from_client_secrets_file(cls, path, scopes):
        return cls()

    def run_local_server(self, *, port, open_browser):
        return self.credentials


def fake_request():
    return object()


def service_builder_calls(bucket):
    def build(api, version, *, credentials, cache_discovery):
        bucket.append((api, version, credentials, cache_discovery))
        return {"api": api, "version": version}
    return build


def config(tmp_path: Path, *, interactive=False, scopes=(GOOGLE_DRIVE_CONTROL_SCOPE,)):
    return GoogleAuthConfig(
        tmp_path / "client.json",
        tmp_path / "token.json",
        allow_interactive=interactive,
        open_browser=False,
        scopes=scopes,
    )


def test_environment_config_requires_private_file_paths():
    with pytest.raises(ValueError):
        GoogleAuthConfig.from_environment({})

    cfg = GoogleAuthConfig.from_environment(
        {
            "TB4_GOOGLE_CLIENT_SECRETS": "/private/client.json",
            "TB4_GOOGLE_TOKEN": "/private/token.json",
        }
    )
    assert str(cfg.client_secrets_path) == "/private/client.json"
    assert str(cfg.token_path) == "/private/token.json"


def test_missing_credentials_is_normalized_without_interactive_side_effect(tmp_path):
    report = build_google_drive_client(
        config(tmp_path),
        credentials_cls=FakeCredentials,
        request_factory=fake_request,
        flow_cls=FakeFlow,
        service_builder=lambda *args, **kwargs: object(),
    )

    assert report.outcome is GoogleAuthOutcome.MISSING_LOCAL_CREDENTIALS
    assert report.service is None


def test_existing_valid_token_builds_drive_v3_client(tmp_path):
    cfg = config(tmp_path)
    cfg.token_path.write_text("{}", encoding="utf-8")
    FakeCredentials.loaded = FakeCredentials(valid=True)
    calls = []

    report = build_google_drive_client(
        cfg,
        credentials_cls=FakeCredentials,
        request_factory=fake_request,
        flow_cls=FakeFlow,
        service_builder=service_builder_calls(calls),
    )

    assert report.outcome is GoogleAuthOutcome.READY
    assert report.ready
    assert calls and calls[0][0:2] == ("drive", "v3")
    assert calls[0][3] is False


def test_expired_refreshable_token_refreshes_and_rewrites_private_cache(tmp_path):
    cfg = config(tmp_path)
    cfg.token_path.write_text("old", encoding="utf-8")
    FakeCredentials.loaded = FakeCredentials(
        valid=False,
        expired=True,
        refresh_token="fake-refresh",
        serialized='{"refreshed":true}',
    )

    report = build_google_drive_client(
        cfg,
        credentials_cls=FakeCredentials,
        request_factory=fake_request,
        flow_cls=FakeFlow,
        service_builder=lambda *args, **kwargs: object(),
    )

    assert report.outcome is GoogleAuthOutcome.READY
    assert report.token_written is True
    assert cfg.token_path.read_text(encoding="utf-8") == '{"refreshed":true}'
    if hasattr(cfg.token_path.stat(), "st_mode"):
        assert cfg.token_path.stat().st_mode & 0o077 == 0


def test_refresh_failure_is_normalized_without_serializing_secret(tmp_path):
    cfg = config(tmp_path)
    cfg.token_path.write_text("SECRET-MARKER", encoding="utf-8")
    FakeCredentials.loaded = FakeCredentials(
        valid=False,
        expired=True,
        refresh_token="refresh-secret-marker",
        refresh_should_fail=True,
    )

    report = build_google_drive_client(
        cfg,
        credentials_cls=FakeCredentials,
        request_factory=fake_request,
        flow_cls=FakeFlow,
        service_builder=lambda *args, **kwargs: object(),
    )

    assert report.outcome is GoogleAuthOutcome.REFRESH_FAILED
    assert "refresh-secret-marker" not in (report.message or "")
    assert "SECRET-MARKER" not in (report.message or "")


def test_client_secrets_present_but_interactive_disabled_reports_required(tmp_path):
    cfg = config(tmp_path)
    cfg.client_secrets_path.write_text('{"installed":{}}', encoding="utf-8")

    report = build_google_drive_client(
        cfg,
        credentials_cls=FakeCredentials,
        request_factory=fake_request,
        flow_cls=FakeFlow,
        service_builder=lambda *args, **kwargs: object(),
    )

    assert report.outcome is GoogleAuthOutcome.INTERACTIVE_REQUIRED


def test_explicit_interactive_flow_writes_token_then_builds_client(tmp_path):
    cfg = config(tmp_path, interactive=True)
    cfg.client_secrets_path.write_text('{"installed":{}}', encoding="utf-8")
    FakeFlow.credentials = FakeCredentials(
        valid=True,
        serialized='{"authorized":true}',
    )

    report = build_google_drive_client(
        cfg,
        credentials_cls=FakeCredentials,
        request_factory=fake_request,
        flow_cls=FakeFlow,
        service_builder=lambda *args, **kwargs: {"drive": "client"},
    )

    assert report.outcome is GoogleAuthOutcome.READY
    assert report.service == {"drive": "client"}
    assert report.token_written
    assert cfg.token_path.read_text(encoding="utf-8") == '{"authorized":true}'


def test_drive_file_scope_is_rejected_for_v1_shared_multi_client_tree(tmp_path):
    calls = []

    report = build_google_drive_client(
        config(
            tmp_path,
            scopes=("https://www.googleapis.com/auth/drive.file",),
        ),
        credentials_cls=FakeCredentials,
        request_factory=fake_request,
        flow_cls=FakeFlow,
        service_builder=service_builder_calls(calls),
    )

    assert report.outcome is GoogleAuthOutcome.UNSUPPORTED_SCOPE
    assert calls == []


def test_invalid_token_file_is_normalized_and_does_not_echo_contents(tmp_path):
    cfg = config(tmp_path)
    cfg.token_path.write_text("TOP-SECRET-BAD-TOKEN", encoding="utf-8")
    FakeCredentials.loaded = None

    report = build_google_drive_client(
        cfg,
        credentials_cls=FakeCredentials,
        request_factory=fake_request,
        flow_cls=FakeFlow,
        service_builder=lambda *args, **kwargs: object(),
    )

    assert report.outcome is GoogleAuthOutcome.INVALID_LOCAL_CREDENTIALS
    assert "TOP-SECRET-BAD-TOKEN" not in (report.message or "")


def test_service_builder_failure_is_normalized(tmp_path):
    cfg = config(tmp_path)
    cfg.token_path.write_text("{}", encoding="utf-8")
    FakeCredentials.loaded = FakeCredentials(valid=True)

    def broken_builder(*args, **kwargs):
        raise RuntimeError("provider says secret-token-value")

    report = build_google_drive_client(
        cfg,
        credentials_cls=FakeCredentials,
        request_factory=fake_request,
        flow_cls=FakeFlow,
        service_builder=broken_builder,
    )

    assert report.outcome is GoogleAuthOutcome.CLIENT_BUILD_FAILED
    assert "secret-token-value" not in (report.message or "")


def test_gitignore_blocks_common_tb4_google_secret_files():
    root = Path(__file__).resolve().parents[2]
    ignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert ".tb4-private/" in ignore
    assert "google-client-secrets.json" in ignore
    assert "google-token.json" in ignore
    assert "credentials.json" in ignore
    assert "token.json" in ignore
