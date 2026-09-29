from __future__ import annotations

from pathlib import Path

from .profile import ProfileError

HTTP_TIMEOUT_S = 20
OAUTH_TIMEOUT_S = 180


def google_backend(config: dict, *, interactive: bool = False):
    """Production authorization with bounded desktop HTTP/OAuth waits."""
    import httplib2
    from google.auth.transport.requests import Request
    from google_auth_httplib2 import AuthorizedHttp
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from tb4.drive.google_backend import GoogleDriveBackend
    from tb4.drive.google_client import GoogleAuthConfig, build_google_drive_client

    class BoundedRequest(Request):
        def __call__(self, *args, **kwargs):
            kwargs["timeout"] = HTTP_TIMEOUT_S
            return super().__call__(*args, **kwargs)

    class BoundedFlow(InstalledAppFlow):
        def run_local_server(self, *args, **kwargs):
            kwargs["timeout_seconds"] = OAUTH_TIMEOUT_S
            kwargs["authorization_prompt_message"] = ""
            kwargs["success_message"] = "TB4 authorization received. You may close this window."
            return super().run_local_server(*args, **kwargs)

        def fetch_token(self, **kwargs):
            kwargs["timeout"] = HTTP_TIMEOUT_S
            return super().fetch_token(**kwargs)

    def builder(api, version, *, credentials, **kwargs):
        http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=HTTP_TIMEOUT_S))
        return build(api, version, http=http, **kwargs)

    drive = config["drive"]
    auth = GoogleAuthConfig(Path(drive["client_secrets_path"]), Path(drive["token_path"]),
                            allow_interactive=interactive, open_browser=interactive)
    report = build_google_drive_client(auth, request_factory=BoundedRequest,
                                       flow_cls=BoundedFlow, service_builder=builder)
    if not report.ready:
        raise ProfileError("AUTH_" + report.outcome.value)
    return GoogleDriveBackend(report.service)
