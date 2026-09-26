from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from tb4.cli import RUNTIME_FACTORIES, _resolve_factory
from tb4.service_host import ServiceHost


SERVICE_NAME = "TB4Fetcher"
SERVICE_DISPLAY_NAME = "TB4 FETCHER"
SERVICE_DESCRIPTION = "TB4 FETCHER target execution service"
DEFAULT_WINDOWS_CONFIG = Path(r"C:\ProgramData\TB4\fetcher.toml")


def config_path_from_environment() -> Path:
    raw = os.environ.get("TB4_FETCHER_CONFIG")
    return Path(raw) if raw else DEFAULT_WINDOWS_CONFIG


def _load_pywin32() -> tuple[Any, Any, Any]:
    if os.name != "nt":
        raise RuntimeError("Windows service support is available only on Windows")
    try:
        import servicemanager
        import win32service
        import win32serviceutil
    except ImportError as exc:
        raise RuntimeError(
            "Windows service support requires the windows extra"
        ) from exc
    return servicemanager, win32service, win32serviceutil


def build_service_class():
    servicemanager, win32service, win32serviceutil = _load_pywin32()

    class TB4FetcherService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args):
            super().__init__(args)
            self._host: ServiceHost | None = None
            self._stop_requested = threading.Event()

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self._stop_requested.set()
            if self._host is not None:
                self._host.request_stop()

        def SvcDoRun(self):
            servicemanager.LogInfoMsg(f"{SERVICE_NAME} starting")
            config_path = config_path_from_environment()
            factory = _resolve_factory(RUNTIME_FACTORIES["fetcher"])
            runtime = factory(config_path)
            host = ServiceHost(runtime, stop_event=self._stop_requested)
            self._host = host
            try:
                host.run(install_signal_handlers=False)
            finally:
                self._host = None
                servicemanager.LogInfoMsg(f"{SERVICE_NAME} stopped")

    return TB4FetcherService


def main(argv: list[str] | None = None) -> int:
    _, _, win32serviceutil = _load_pywin32()
    service_class = build_service_class()
    win32serviceutil.HandleCommandLine(service_class, argv=argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
