from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
OBS = ROOT / "protocol" / "device-observation.yaml"
MACHINES = ROOT / "protocol" / "state-machines.yaml"
OBJECTS = ROOT / "protocol" / "objects.yaml"


def _yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_fresh_pulse_is_fetcher_readiness_authority() -> None:
    data = _yaml(OBS)
    rule = data["resolution"][0]
    assert rule["when"]["dog_pulse"] == "FRESH"
    assert rule["conclude"]["fetcher"] == "READY"


def test_online_sniff_without_fresh_pulse_is_not_fetcher_ready() -> None:
    data = _yaml(OBS)
    rule = data["resolution"][1]
    assert rule["when"] == {
        "dog_pulse": "STALE_OR_MISSING",
        "dog_sniff": "ONLINE",
    }
    assert rule["conclude"]["fetcher"] == "NOT_READY"
    assert rule["conclude"]["host"] == "ONLINE"


def test_absence_is_unknown_not_offline() -> None:
    data = _yaml(OBS)
    assert data["conflict_rules"]["no_observation_is_not_offline"]["result"] == "UNKNOWN"


def test_sniff_uses_write_on_change_semantics() -> None:
    rules = _yaml(OBS)["publication"]["dog_sniff"]
    assert rules["local_probe_may_be_frequent"] is True
    assert rules["remote_write_on_unchanged_probe"] is False
    assert rules["periodic_freshness_republish"] is True


def test_target_leash_is_registered_and_not_global() -> None:
    objects = _yaml(OBJECTS)["stateful_objects"]["TARGET_LEASH"]
    assert objects["filenames"] == {
        "CLEAR": "LEASH_CLEAR",
        "TANGLED": "LEASH_TANGLED",
    }
    machine = _yaml(MACHINES)["state_machines"]["TARGET_LEASH"]
    assert machine["scope_rules"]["global_blocking"] is False


def test_offline_and_job_failures_do_not_tangle_leash_by_themselves() -> None:
    machine = _yaml(MACHINES)["state_machines"]["TARGET_LEASH"]
    nonfaults = set(machine["scope_rules"]["examples"]["not_tangled_by_itself"])
    assert {
        "host_temporarily_offline",
        "wake_timeout",
        "one_job_failed",
        "one_job_partial",
        "one_job_gone",
    } <= nonfaults
