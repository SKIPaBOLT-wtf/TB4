from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from tb4.cli import DEFAULT_CONFIG, build_parser
from tb4.service_host import ServiceHost


ROOT = Path(__file__).resolve().parents[2]
SYSTEMD = ROOT / "packaging" / "systemd"


class FakeRuntime:
    def __init__(self) -> None:
        self.stop_seen = False

    def run(self, stop_event) -> int:
        self.stop_seen = stop_event.is_set()
        return 0


@pytest.mark.parametrize(
    ("unit_name", "role", "config_path"),
    [
        ("tb4-watchdog.service", "watchdog", "/etc/tb4/watchdog.toml"),
        ("tb4-fetcher.service", "fetcher", "/etc/tb4/fetcher.toml"),
    ],
)
def test_systemd_units_are_generic_and_externalize_config(
    unit_name: str,
    role: str,
    config_path: str,
) -> None:
    text = (SYSTEMD / unit_name).read_text(encoding="utf-8")
    assert "User=tb4" in text
    assert "Group=tb4" in text
    assert "EnvironmentFile=-/etc/tb4/tb4.env" in text
    assert f"ExecStart=/usr/bin/env tb4 {role} --config {config_path}" in text
    assert "KillMode=mixed" in text
    assert "password" not in text.lower()
    assert "private_key" not in text.lower()


def test_cli_defaults_are_deterministic_absolute_paths() -> None:
    parser = build_parser()
    watchdog = parser.parse_args(["watchdog", "--check"])
    fetcher = parser.parse_args(["fetcher", "--check"])
    assert watchdog.config == DEFAULT_CONFIG["watchdog"]
    assert fetcher.config == DEFAULT_CONFIG["fetcher"]
    # These are systemd/Linux defaults even when source tests run on Windows.
    assert PurePosixPath(watchdog.config.as_posix()).is_absolute()
    assert PurePosixPath(fetcher.config.as_posix()).is_absolute()


def test_service_host_cleanup_is_lifo_and_exactly_once() -> None:
    runtime = FakeRuntime()
    order: list[str] = []
    host = ServiceHost(runtime)
    host.add_cleanup(lambda: order.append("first"))
    host.add_cleanup(lambda: order.append("second"))

    assert host.run(install_signal_handlers=False) == 0
    host.shutdown()

    assert order == ["second", "first"]
    assert host.stop_event.is_set()
