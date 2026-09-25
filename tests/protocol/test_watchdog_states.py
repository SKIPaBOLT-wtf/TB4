from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "protocol" / "state-machines.yaml"


def _machines() -> dict:
    with SPEC.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["state_machines"]


def _edges(name: str) -> set[tuple[str, str, str]]:
    return {
        (edge["from"], edge["to"], edge["actor"])
        for edge in _machines()[name]["transitions"]
    }


def test_watchdog_mode_uses_canonical_dog_names() -> None:
    mode = _machines()["WATCHDOG_MODE"]
    assert mode["states"]["SNOOZE"]["filename"] == "DOG_SNOOZE"
    assert mode["states"]["AWAKE"]["filename"] == "DOG_AWAKE"
    assert mode["mode_rules"]["mode_is_health"] is False


def test_watchdog_mode_is_owned_by_watchdog() -> None:
    assert _edges("WATCHDOG_MODE") == {
        ("SNOOZE", "AWAKE", "WATCHDOG"),
        ("AWAKE", "SNOOZE", "WATCHDOG"),
    }


def test_dog_shit_requires_review_then_revalidation() -> None:
    edges = _edges("WATCHDOG_FAULT")
    assert ("CLEAN", "BLOCKING", "WATCHDOG") in edges
    assert ("BLOCKING", "REVIEWED", "COACH") in edges
    assert ("REVIEWED", "CLEAN", "WATCHDOG") in edges
    assert ("REVIEWED", "BLOCKING", "WATCHDOG") in edges


def test_ordinary_target_failures_are_not_global_dog_shit() -> None:
    nonblocking = set(
        _machines()["WATCHDOG_FAULT"]["fault_scope"][
            "explicitly_nonblocking_examples"
        ]
    )
    assert {
        "one_target_offline",
        "wol_failed",
        "ssh_bootstrap_failed",
        "one_fetch_ball_failed",
        "one_fetch_ball_partial",
        "one_fetch_ball_gone",
        "one_wake_bone_failed",
    } <= nonblocking


def test_blocking_disables_new_control_work_but_keeps_repair_possible() -> None:
    rules = _machines()["WATCHDOG_FAULT"]["blocking_rules"]
    assert rules["new_control_work_allowed_in_BLOCKING"] is False
    assert rules["diagnostic_reads_allowed_in_BLOCKING"] is True
    assert rules["repair_actions_allowed_in_BLOCKING"] is True
    assert rules["timeout_alone_clears_fault"] is False
    assert rules["clear_requires_invariant_revalidation"] is True
