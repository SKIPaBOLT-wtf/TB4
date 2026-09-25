from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = ROOT / "config" / "defaults.toml"
RULES = ROOT / "protocol" / "config-rules.yaml"


def _config() -> dict:
    return tomllib.loads(DEFAULTS.read_text(encoding="utf-8"))


def _rules() -> dict:
    return yaml.safe_load(RULES.read_text(encoding="utf-8"))


def _resolve_ref(config: dict, ref: str) -> Any:
    value: Any = config
    for part in ref.split("."):
        value = value[part]
    return value


def _value(expr: Any, config: dict) -> Any:
    if isinstance(expr, (int, float)):
        return expr
    if isinstance(expr, dict) and "ref" in expr:
        return _resolve_ref(config, expr["ref"])
    if not isinstance(expr, dict):
        raise AssertionError(f"Unsupported value expression: {expr!r}")

    op = expr["op"]
    if op == "mul":
        values = [_value(item, config) for item in expr["args"]]
        result = 1
        for value in values:
            result *= value
        return result
    if op == "add":
        return sum(_value(item, config) for item in expr["args"])
    if op == "sum":
        return sum(_value(item, config) for item in _value(expr["value"], config))
    raise AssertionError(f"Unsupported arithmetic expression: {op}")


def _passes(check: dict, config: dict) -> bool:
    op = check["op"]
    if op == "gte":
        return _value(check["left"], config) >= _value(check["right"], config)
    if op == "lte":
        return _value(check["left"], config) <= _value(check["right"], config)
    if op == "nondecreasing":
        values = _value(check["value"], config)
        return values == sorted(values)
    raise AssertionError(f"Unsupported rule operation: {op}")


def _rule(rule_id: str) -> dict:
    return next(rule for rule in _rules()["rules"] if rule["id"] == rule_id)


def test_rule_spec_has_unique_ids_and_known_severities() -> None:
    spec = _rules()
    ids = [rule["id"] for rule in spec["rules"]]
    assert len(ids) == len(set(ids))
    assert all(rule["severity"] in {"FATAL", "WARNING"} for rule in spec["rules"])
    runtime_ids = [rule["id"] for rule in spec["runtime_invariants"]]
    assert len(runtime_ids) == len(set(runtime_ids))
    assert set(ids).isdisjoint(runtime_ids)


def test_rules_reference_configuration_only_and_have_no_rule_dependencies() -> None:
    rule_ids = {rule["id"] for rule in _rules()["rules"]}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if "ref" in value:
                assert value["ref"] not in rule_ids
                assert "." in value["ref"]
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for rule in _rules()["rules"]:
        walk(rule["check"])


def test_canonical_defaults_satisfy_all_fatal_rules() -> None:
    config = _config()
    failures = [
        rule["id"]
        for rule in _rules()["rules"]
        if rule["severity"] == "FATAL" and not _passes(rule["check"], config)
    ]
    assert failures == []


@pytest.mark.parametrize(
    ("rule_id", "path", "bad_value"),
    [
        ("WATCHDOG_IDLE_STALE_MARGIN", "watchdog.stale_idle_s", 60),
        ("WATCHDOG_ACTIVE_STALE_MARGIN", "watchdog.stale_active_s", 20),
        ("WAKE_HAS_MULTIPLE_PROBE_OPPORTUNITIES", "wake.wake_deadline_s", 20),
        ("GONE_GRACE_EXCEEDS_BUSY_PULSE_JITTER", "fetcher.gone_grace_s", 10),
        ("FETCHER_IDLE_EXIT_SPANS_HEARTBEATS", "fetcher.idle_exit_s", 60),
        ("DEFAULT_RUN_LIMIT_WITHIN_MAXIMUM", "job.default_run_limit_s", 22000),
        ("MAX_RUN_LIMIT_WITHIN_PROTOCOL_CEILING", "job.max_run_limit_s", 90000),
        ("ACCEPT_TTL_NOT_LONGER_THAN_MAX_RUNTIME", "job.accept_ttl_s", 22000),
        ("DRIVE_TRANSITION_ATTEMPTS_BOUNDED", "drive.transition_attempts", 6),
    ],
)
def test_constructed_unsafe_config_fails_expected_rule(
    rule_id: str, path: str, bad_value: int
) -> None:
    config = _config()
    section, key = path.split(".")
    config[section][key] = bad_value
    assert not _passes(_rule(rule_id)["check"], config)


def test_decreasing_drive_backoff_is_fatal() -> None:
    config = _config()
    config["drive"]["confirm_backoff_ms"] = [1000, 500]
    assert not _passes(_rule("DRIVE_CONFIRM_BACKOFF_NONDECREASING")["check"], config)


def test_excessive_total_drive_confirmation_budget_is_fatal() -> None:
    config = _config()
    config["drive"]["confirm_backoff_ms"] = [10000, 20000]
    config["drive"]["transition_attempts"] = 3
    assert not _passes(_rule("DRIVE_TOTAL_CONFIRM_BUDGET_BOUNDED")["check"], config)


def test_warning_rule_does_not_define_startup_rejection() -> None:
    spec = _rules()
    assert spec["semantics"]["fatal_action"] == "reject_startup"
    assert spec["semantics"]["warning_action"] == "report_and_continue"
    assert any(rule["severity"] == "WARNING" for rule in spec["rules"])


def test_runtime_invariants_are_explicitly_owned() -> None:
    invariants = {item["id"]: item for item in _rules()["runtime_invariants"]}
    assert invariants["IDLE_TIMER_PAUSES_DURING_ACTIVE_WORK"]["owner"] == "FETCHER"
    assert invariants["GONE_REQUIRES_STALE_EXECUTION_EVIDENCE"]["owner"] == "WATCHDOG"
    assert invariants["CURRENT_TIME_EXPIRY_IS_RUNTIME_ONLY"]["owner"] == "DeadlineGuard"
