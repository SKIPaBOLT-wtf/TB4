from __future__ import annotations

from pathlib import Path

import pytest

from tb4.cli import run_role
from tb4.pilot.config_builder import load_and_build, write_private_configs
from tb4.runtime_support import RuntimeConfigurationError


ROOT = Path(__file__).resolve().parents[2]
PILOT_EXAMPLE = ROOT / "config" / "examples" / "pilot.example.toml"


def test_generated_role_configs_pass_stable_cli_check(tmp_path: Path) -> None:
    generated = load_and_build(PILOT_EXAMPLE)
    watchdog, fetcher = write_private_configs(generated, tmp_path / "private")

    assert run_role("watchdog", watchdog.resolve(), check_only=True) == 0
    assert run_role("fetcher", fetcher.resolve(), check_only=True) == 0


def test_fetcher_check_rejects_structurally_incomplete_config(tmp_path: Path) -> None:
    path = tmp_path / "fetcher.toml"
    path.write_text(
        """
[identity]
device_id = "target-a"

[drive]
root_id = "root-only"
""",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeConfigurationError):
        run_role("fetcher", path.resolve(), check_only=True)


def test_watchdog_check_rejects_unbounded_discovery_scope(tmp_path: Path) -> None:
    generated = load_and_build(PILOT_EXAMPLE)
    watchdog, _ = write_private_configs(generated, tmp_path / "private")
    text = watchdog.read_text(encoding="utf-8").replace(
        "discovery_cidrs = []",
        'discovery_cidrs = ["192.0.2.0/24"]',
    ).replace(
        "discovery_max_hosts = 1024",
        "discovery_max_hosts = 10",
    )
    watchdog.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="max_hosts"):
        run_role("watchdog", watchdog.resolve(), check_only=True)
