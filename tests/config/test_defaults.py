from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = ROOT / "config" / "defaults.toml"


def _config() -> dict:
    return tomllib.loads(DEFAULTS.read_text(encoding="utf-8"))


def test_defaults_parse_and_have_required_sections() -> None:
    config = _config()
    assert set(config) == {
        "drive",
        "watchdog",
        "network",
        "wake",
        "fetcher",
        "job",
        "retention",
    }


def test_drive_retries_are_bounded() -> None:
    drive = _config()["drive"]
    assert drive["transition_attempts"] == 3
    assert 1 <= drive["transition_attempts"] <= 10
    assert 1 <= len(drive["confirm_backoff_ms"]) <= 10
    assert all(isinstance(value, int) and value > 0 for value in drive["confirm_backoff_ms"])
    assert drive["confirm_backoff_ms"] == sorted(drive["confirm_backoff_ms"])


def test_watchdog_timing_defaults_are_positive_and_conservative() -> None:
    watchdog = _config()["watchdog"]
    assert watchdog["heartbeat_idle_s"] > 0
    assert watchdog["heartbeat_active_s"] > 0
    assert watchdog["stale_idle_s"] > watchdog["heartbeat_idle_s"]
    assert watchdog["stale_active_s"] > watchdog["heartbeat_active_s"]
    assert watchdog["awake_lease_s"] > 0
    assert watchdog["clock_skew_tolerance_s"] > 0


def test_network_and_wake_defaults_are_bounded() -> None:
    config = _config()
    network = config["network"]
    wake = config["wake"]
    assert network["known_device_probe_s"] > 0
    assert network["known_device_publish_s"] >= network["known_device_probe_s"]
    assert network["stray_scan_s"] >= network["known_device_probe_s"]
    assert wake["wol_initial_wait_s"] > 0
    assert wake["probe_interval_s"] > 0
    assert wake["wake_deadline_s"] > wake["wol_initial_wait_s"]


def test_fetcher_idle_exit_is_not_shorter_than_idle_heartbeat() -> None:
    fetcher = _config()["fetcher"]
    assert fetcher["busy_heartbeat_s"] > 0
    assert fetcher["idle_heartbeat_s"] > 0
    assert fetcher["idle_exit_s"] > fetcher["idle_heartbeat_s"]
    assert fetcher["gone_grace_s"] > 0


def test_job_defaults_have_explicit_safety_ceiling() -> None:
    job = _config()["job"]
    assert 0 < job["accept_ttl_s"]
    assert 0 < job["default_run_limit_s"] <= job["max_run_limit_s"] <= 86400
    assert 0 < job["inline_result_max_bytes"] <= 1024 * 1024
    assert 0 < job["inline_payload_max_chars"] <= 65536
    assert 0 < job["result_tail_max_chars"] <= job["inline_result_max_bytes"]


def test_retention_defaults_are_finite() -> None:
    retention = _config()["retention"]
    assert 1 <= retention["boneyard_days"] <= 30
    assert 1 <= retention["toy_box_days"] <= 30
    assert retention["sweep_interval_s"] > 0
