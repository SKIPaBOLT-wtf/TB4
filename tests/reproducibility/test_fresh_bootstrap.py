from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

from tb4.fetcher.execution_models import ExecutionDisposition
from tb4.testing.simulation import SimulationHarness, execution_report


ROOT = Path(__file__).resolve().parents[2]


def test_public_safe_example_configs_parse_without_private_values() -> None:
    examples = ROOT / "config" / "examples"
    for name in ("watchdog.toml.example", "fetcher.toml.example"):
        path = examples / name
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        assert data["drive"]["root_id"] == "replace-at-deploy-time"
        text = path.read_text(encoding="utf-8")
        assert "192.168." not in text
        assert "10.0." not in text
        assert "SKIPaBOLT" not in text


def test_fresh_demo_bootstrap_requires_no_conversation_only_root_id() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "bootstrap_drive.py"), "--demo-memory"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["root_id"] == "mem-000001"
    assert report["created_count"] > 0
    assert report["park_map_generation"] == 0


def test_fresh_synthetic_job_round_trip_recycles_to_ready() -> None:
    sim = SimulationHarness()
    target = sim.add_target("target-a", online=True)
    sim.publish_pulse(target)

    sim.toss_job(target)
    result = sim.run_job(
        target,
        execution_report(ExecutionDisposition.EXITED, exit_code=0),
    )

    assert result.terminal_state == "DONE"
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_DONE"

    sim.recycle_job(target)
    assert sim.state(target.fetch_ball_id) == "FETCH_BALL_READY"
