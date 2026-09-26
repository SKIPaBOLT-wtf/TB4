from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from tb4.pilot.config_builder import load_and_build, write_private_configs


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "config" / "examples" / "pilot.example.toml"


def test_public_pilot_template_generates_both_role_configs() -> None:
    generated = load_and_build(EXAMPLE)
    watchdog = tomllib.loads(generated.watchdog)
    fetcher = tomllib.loads(generated.fetcher)

    assert watchdog["targets"][0]["device_id"] == "target-a"
    assert fetcher["identity"]["device_id"] == "target-a"
    assert watchdog["drive"]["root_id"] == fetcher["drive"]["root_id"]
    assert watchdog["targets"][0]["device_key"] == "target-a"


def test_private_writer_creates_two_parseable_files(tmp_path: Path) -> None:
    generated = load_and_build(EXAMPLE)
    watchdog_path, fetcher_path = write_private_configs(generated, tmp_path / "private")

    assert tomllib.loads(watchdog_path.read_text(encoding="utf-8"))
    assert tomllib.loads(fetcher_path.read_text(encoding="utf-8"))
    if os.name == "posix":
        assert watchdog_path.stat().st_mode & 0o077 == 0
        assert fetcher_path.stat().st_mode & 0o077 == 0


def test_prepare_pilot_cli_does_not_echo_private_values(tmp_path: Path) -> None:
    text = EXAMPLE.read_text(encoding="utf-8").replace(
        "replace-at-deploy-time",
        "private-value-do-not-echo",
    )
    config = tmp_path / "pilot.toml"
    config.write_text(text, encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "prepare_pilot.py"),
            "--config",
            str(config),
            "--output-dir",
            str(tmp_path / "generated"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "private-value-do-not-echo" not in completed.stdout
    assert "private-value-do-not-echo" not in completed.stderr
    assert (tmp_path / "generated" / "watchdog.toml").is_file()
    assert (tmp_path / "generated" / "fetcher.toml").is_file()
