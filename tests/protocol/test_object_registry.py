from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "protocol" / "objects.yaml"


def _registry() -> dict:
    with REGISTRY.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _active_names(data: dict) -> list[str]:
    names = list(data["fixed_objects"].keys())
    for root, definition in data["stateful_objects"].items():
        if "filenames" in definition:
            names.extend(definition["filenames"].values())
            continue
        root_name = definition.get("root_name", root)
        names.extend(f"{root_name}_{state}" for state in definition["states"])
    return names


def test_registry_has_unique_active_names() -> None:
    names = _active_names(_registry())
    assert len(names) == len(set(names))


def test_required_humorous_names_are_canonical() -> None:
    names = set(_active_names(_registry()))
    assert "WAKE_BONE_TOSS" in names
    assert "FETCH_BALL_CHEW" in names
    assert "DOG_SNOOZE" in names
    assert "DOG_SHIT_BLOCKING" in names


def test_rejected_draft_names_are_not_active() -> None:
    names = set(_active_names(_registry()))
    rejected = {
        "WAKE_BONE_THROWN",
        "FETCH_BALL_THROWN",
        "FETCH_BALL_CHEWING",
        "DOG_MODE_NAPPING",
    }
    assert names.isdisjoint(rejected)


def test_active_control_names_are_deterministic() -> None:
    names = _active_names(_registry())
    forbidden_fragments = ("{", "}", "<", ">", "%", "*")
    for name in names:
        assert name == name.upper()
        assert all(fragment not in name for fragment in forbidden_fragments)


def test_roles_are_distinct_and_required() -> None:
    roles = set(_registry()["roles"])
    assert roles == {"COACH", "WATCHDOG", "FETCHER", "RUNNER"}
