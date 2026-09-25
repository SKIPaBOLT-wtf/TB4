from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from tb4.core.spec_validation import validate_protocol


ROOT = Path(__file__).resolve().parents[2]


def _copy_spec(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "protocol", root / "protocol")
    shutil.copytree(ROOT / "config", root / "config")
    return root


def test_canonical_repository_protocol_passes() -> None:
    report = validate_protocol(ROOT)
    assert report.errors == ()


def test_cli_exits_zero_for_canonical_repository() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_protocol.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TB4 protocol validation OK" in result.stdout


def test_unknown_transition_state_is_reported(tmp_path: Path) -> None:
    root = _copy_spec(tmp_path)
    path = root / "protocol" / "state-machines.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["state_machines"]["FETCH_BALL"]["transitions"][0]["to"] = "LOST_SOCK"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    report = validate_protocol(root)
    messages = [item.format() for item in report.errors]
    assert any("unknown state 'LOST_SOCK'" in message for message in messages)


def test_unknown_tree_logical_object_is_reported(tmp_path: Path) -> None:
    root = _copy_spec(tmp_path)
    path = root / "protocol" / "tree-blueprint.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["subtrees"]["DEVICE_TREE"]["children"]["DOG_TAG"]["logical_object"] = "MYSTERY_DOG"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    report = validate_protocol(root)
    assert any("unknown fixed object 'MYSTERY_DOG'" in item.message for item in report.errors)


def test_unknown_config_reference_is_reported(tmp_path: Path) -> None:
    root = _copy_spec(tmp_path)
    path = root / "protocol" / "config-rules.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["rules"][0]["check"]["left"] = {"ref": "watchdog.missing_setting_s"}
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    report = validate_protocol(root)
    assert any("unknown configuration reference" in item.message for item in report.errors)


def test_fatal_config_rule_violation_is_an_error(tmp_path: Path) -> None:
    root = _copy_spec(tmp_path)
    path = root / "config" / "defaults.toml"
    text = path.read_text(encoding="utf-8")
    text = text.replace("stale_active_s = 35", "stale_active_s = 20")
    path.write_text(text, encoding="utf-8")

    report = validate_protocol(root)
    assert any("WATCHDOG_ACTIVE_STALE_MARGIN" in item.message for item in report.errors)


def test_warning_config_rule_does_not_fail_validation(tmp_path: Path) -> None:
    root = _copy_spec(tmp_path)
    path = root / "config" / "defaults.toml"
    text = path.read_text(encoding="utf-8")
    text = text.replace("known_device_publish_s = 300", "known_device_publish_s = 10")
    path.write_text(text, encoding="utf-8")

    report = validate_protocol(root)
    assert report.errors == ()
    assert any(
        "UNCHANGED_SNIFF_PUBLISH_NOT_FASTER_THAN_PROBE" in item.message
        for item in report.warnings
    )


def test_duplicate_yaml_mapping_key_is_rejected(tmp_path: Path) -> None:
    root = _copy_spec(tmp_path)
    path = root / "protocol" / "objects.yaml"
    text = path.read_text(encoding="utf-8")
    text += "\nroles:\n  EXTRA: {}\n"
    path.write_text(text, encoding="utf-8")

    report = validate_protocol(root)
    assert any("duplicate mapping key 'roles'" in item.message for item in report.errors)


def test_missing_required_schema_is_reported(tmp_path: Path) -> None:
    root = _copy_spec(tmp_path)
    (root / "protocol" / "schemas" / "fetch-ball.schema.json").unlink()

    report = validate_protocol(root)
    assert any(
        item.path == "fetch-ball.schema.json" and "required canonical schema" in item.message
        for item in report.errors
    )


def test_multiple_independent_errors_are_collected(tmp_path: Path) -> None:
    root = _copy_spec(tmp_path)

    state_path = root / "protocol" / "state-machines.yaml"
    states = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    states["state_machines"]["FETCH_BALL"]["initial_state"] = "LOST_SOCK"
    state_path.write_text(yaml.safe_dump(states, sort_keys=False), encoding="utf-8")

    (root / "protocol" / "schemas" / "stop-ball.schema.json").unlink()

    report = validate_protocol(root)
    messages = [item.format() for item in report.errors]
    assert any("unknown initial state 'LOST_SOCK'" in message for message in messages)
    assert any("stop-ball.schema.json" in message for message in messages)


def test_validator_does_not_modify_specs(tmp_path: Path) -> None:
    root = _copy_spec(tmp_path)
    before = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    validate_protocol(root)
    after = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }
    assert before == after
