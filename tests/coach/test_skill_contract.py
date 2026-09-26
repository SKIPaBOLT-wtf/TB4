from __future__ import annotations

import re
from pathlib import Path

import yaml

from tb4.security import scan_text


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skill" / "tb4" / "SKILL.md"


def _state_spec() -> dict:
    return yaml.safe_load((ROOT / "protocol/state-machines.yaml").read_text(encoding="utf-8"))


def _coach_spec() -> dict:
    return yaml.safe_load((ROOT / "protocol/coach-workflows.yaml").read_text(encoding="utf-8"))


def test_skill_has_valid_minimal_metadata_and_required_agent_metadata() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["name"] == "tb4"
    description = frontmatter["description"]
    assert "Drive-native terminal bridge" in description
    assert "wake" in description
    assert "cancel" in description
    assert "recover" in description

    agent = yaml.safe_load(
        (ROOT / "skill/tb4/agents/openai.yaml").read_text(encoding="utf-8")
    )
    assert agent["interface"]["display_name"] == "TB4"
    assert agent["interface"]["short_description"]


def test_skill_is_compact_and_progressively_loads_canonical_sources() -> None:
    text = SKILL.read_text(encoding="utf-8")
    source_map = (ROOT / "skill/tb4/references/source-map.md").read_text(
        encoding="utf-8"
    )

    assert len(text.splitlines()) < 220
    assert "docs/START_HERE.md" in text
    assert "docs/COACH.md" in text
    assert "protocol/state-machines.yaml" in text
    assert "PARK_MAP" in text
    assert "protocol/state-machines.yaml" in source_map
    assert "config/defaults.toml" in source_map


def test_skill_fetch_ball_state_names_are_canonical() -> None:
    text = SKILL.read_text(encoding="utf-8")
    canonical = set(_state_spec()["state_machines"]["FETCH_BALL"]["states"])
    referenced = set(re.findall(r"FETCH_BALL_([A-Z]+)", text))

    assert referenced
    assert referenced <= canonical


def test_coach_scenario_conditions_reference_canonical_states() -> None:
    protocol = _state_spec()["state_machines"]
    scenarios = _coach_spec()["scenarios"]

    state_keys = {
        "watchdog_fault": set(protocol["WATCHDOG_FAULT"]["states"]),
        "fetch_ball": set(protocol["FETCH_BALL"]["states"]),
        "wake_bone": set(protocol["WAKE_BONE"]["states"]),
        "stop_ball": set(protocol["STOP_BALL"]["states"]),
    }

    for scenario in scenarios.values():
        for key, value in scenario["conditions"].items():
            if key in state_keys:
                assert value in state_keys[key]


def test_representative_workflows_encode_required_safety_branches() -> None:
    scenarios = _coach_spec()["scenarios"]

    assert scenarios["ready_target_job"]["coach_actions"] == [
        "reserve_fetch_ball",
        "write_and_verify_request",
        "publish_fetch_ball_toss",
        "wait_for_terminal_state",
        "interpret_terminal_evidence",
        "recycle_after_consumption",
    ]

    sleeping = scenarios["sleeping_target_job"]["coach_actions"]
    assert sleeping.index("wait_for_fresh_dog_pulse") < sleeping.index(
        "dispatch_fetch_ball_after_ready"
    )

    partial = scenarios["partial_result"]["coach_actions"]
    assert "inspect_completed_effects" in partial
    assert "never_implicitly_replay" in partial

    gone = scenarios["gone_mutating_result"]["coach_actions"]
    assert "inspect_current_target_state" in gone
    assert "never_implicitly_replay" in gone

    blocked = scenarios["watchdog_blocking"]["coach_actions"]
    assert blocked[0] == "refuse_new_normal_control_work"
    assert "require_watchdog_revalidation_before_clean" in blocked


def test_skill_forbids_ssh_payload_transport_and_busy_polling() -> None:
    text = SKILL.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "ssh is a fixed service-bootstrap mechanism only" in lowered
    assert "never send arbitrary job scripts through ssh" in lowered
    assert "never claim background monitoring" in lowered
    assert "do not use folder scans as a substitute for waiting" in lowered


def test_skill_source_contains_no_public_repo_security_findings() -> None:
    findings = []
    for path in (
        ROOT / "skill/tb4/SKILL.md",
        ROOT / "skill/tb4/references/source-map.md",
        ROOT / "skill/tb4/agents/openai.yaml",
        ROOT / "docs/COACH.md",
        ROOT / "protocol/coach-workflows.yaml",
    ):
        findings.extend(
            scan_text(
                path.relative_to(ROOT).as_posix(),
                path.read_text(encoding="utf-8"),
            )
        )
    assert findings == []


def test_skill_does_not_bundle_protocol_duplicate_or_execution_scripts() -> None:
    skill_root = ROOT / "skill/tb4"
    assert not (skill_root / "scripts").exists()
    assert not (skill_root / "assets").exists()

    # The Skill points at canonical protocol sources instead of bundling a stale
    # second state-machine/schema copy.
    bundled = {
        path.name
        for path in skill_root.rglob("*")
        if path.is_file()
    }
    assert "state-machines.yaml" not in bundled
    assert not any(name.endswith(".schema.json") for name in bundled)
