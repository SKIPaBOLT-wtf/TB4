from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT = ROOT / "protocol" / "tree-blueprint.yaml"
OBJECTS = ROOT / "protocol" / "objects.yaml"


def _yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _registered_objects() -> set[str]:
    registry = _yaml(OBJECTS)
    return set(registry["fixed_objects"]) | set(registry["stateful_objects"])


def _walk_children(node: dict) -> list[dict]:
    found: list[dict] = []
    for name, child in node.get("children", {}).items():
        found.append({"name": name, **child})
        found.extend(_walk_children(child))
    return found


def test_root_is_never_auto_recreated() -> None:
    root = _yaml(BLUEPRINT)["root"]
    assert root["repair_policy"] == "never_auto_recreate"
    assert _yaml(BLUEPRINT)["invariants"]["root_never_auto_recreated"] is True


def test_top_level_static_children_are_unique() -> None:
    children = list(_yaml(BLUEPRINT)["root"]["children"])
    assert len(children) == len(set(children))


def test_all_logical_object_references_exist_in_registry() -> None:
    data = _yaml(BLUEPRINT)
    registered = _registered_objects()
    refs = []
    refs.extend(
        node["logical_object"]
        for node in _walk_children(data["root"])
        if "logical_object" in node
    )
    for subtree in data["subtrees"].values():
        refs.extend(
            node["logical_object"]
            for node in _walk_children(subtree)
            if "logical_object" in node
        )
    assert refs
    assert set(refs) <= registered


def test_every_required_static_node_has_repair_policy() -> None:
    data = _yaml(BLUEPRINT)
    nodes = _walk_children(data["root"])
    for subtree in data["subtrees"].values():
        nodes.extend(_walk_children(subtree))
    for node in nodes:
        if node.get("required") and node["kind"] != "fixed_object":
            assert node.get("repair_policy"), node["name"]


def test_device_work_channels_are_exactly_one_in_v1() -> None:
    device = _yaml(BLUEPRINT)["subtrees"]["DEVICE_TREE"]
    playground = device["children"]["PLAYGROUND"]["children"]
    assert playground["FETCH_BALL"]["multiplicity"] == "exactly_one"
    assert playground["STOP_BALL"]["multiplicity"] == "exactly_one"
    assert _yaml(BLUEPRINT)["invariants"]["one_work_thread_per_device_v1"] is True


def test_artifact_and_history_paths_are_not_live_control_paths() -> None:
    device = _yaml(BLUEPRINT)["subtrees"]["DEVICE_TREE"]["children"]
    assert device["TOY_BOX"]["control_path"] is False
    assert device["BONEYARD"]["control_path"] is False


def test_hostname_change_does_not_rename_registered_device_folder() -> None:
    device = _yaml(BLUEPRINT)["root"]["children"]["BALL_PARK"]["dynamic_children"]["DEVICE"]
    assert device["auto_rename_on_hostname_change"] is False
    assert _yaml(BLUEPRINT)["invariants"]["device_folder_name_is_identity"] is False
