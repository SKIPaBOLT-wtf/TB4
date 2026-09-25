from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tb4.core.schemas import canonical_json_text
from tb4.drive.backend import DriveBackend, ObjectMetadata
from tb4.drive.errors import BackendOutcome
from tb4.drive.park_map import GLOBAL_REFERENCES, ParkMap


class BootstrapError(RuntimeError):
    pass


class BootstrapConflict(BootstrapError):
    pass


@dataclass(frozen=True, slots=True)
class BootstrapReport:
    root_id: str
    park_map: ParkMap
    created_count: int
    reused_count: int


def canonical_blueprint_path() -> Path:
    return Path(__file__).resolve().parents[3] / "protocol" / "tree-blueprint.yaml"


def _load_blueprint(path: Path | None = None) -> dict[str, Any]:
    resolved = canonical_blueprint_path() if path is None else path.resolve()
    return yaml.safe_load(resolved.read_text(encoding="utf-8"))


def _list_exact_name(
    backend: DriveBackend,
    parent_id: str,
    name: str,
) -> list[ObjectMetadata]:
    result = backend.list_children(parent_id)
    if not result.ok:
        raise BootstrapError(
            f"cannot enumerate verified parent {parent_id!r}: "
            f"{result.outcome.value}: {result.message or ''}"
        )
    assert result.value is not None
    return [child for child in result.value if child.name == name]


def _ensure_child(
    backend: DriveBackend,
    *,
    parent_id: str,
    name: str,
    is_folder: bool,
    initial_text: str = "{}\n",
) -> tuple[ObjectMetadata, bool]:
    matches = _list_exact_name(backend, parent_id, name)
    if len(matches) > 1:
        raise BootstrapConflict(
            f"ambiguous child {name!r} under parent {parent_id!r}: "
            f"{len(matches)} matches"
        )
    if matches:
        match = matches[0]
        if match.is_folder != is_folder:
            raise BootstrapConflict(
                f"existing child {name!r} has wrong kind"
            )
        return match, False

    created = (
        backend.create_folder(parent_id, name)
        if is_folder
        else backend.create_text(parent_id, name, initial_text)
    )
    if created.ok:
        assert created.value is not None
        return created.value.metadata, True

    if created.outcome is BackendOutcome.AMBIGUOUS:
        matches = _list_exact_name(backend, parent_id, name)
        if len(matches) == 1 and matches[0].is_folder == is_folder:
            return matches[0], True
        if len(matches) > 1:
            raise BootstrapConflict(
                f"ambiguous create produced duplicate child {name!r}"
            )
        raise BootstrapError(
            f"ambiguous create for {name!r} could not be reconciled"
        )

    raise BootstrapError(
        f"failed to create {name!r}: {created.outcome.value}: "
        f"{created.message or ''}"
    )


def _verify_explicit_root(backend: DriveBackend, root_id: str | None) -> ObjectMetadata:
    if not root_id:
        raise BootstrapError(
            "explicit existing root_id is required; bootstrap never creates a root"
        )
    result = backend.get_metadata(root_id)
    if not result.ok:
        raise BootstrapError(
            f"configured root {root_id!r} is not reachable: {result.outcome.value}"
        )
    assert result.value is not None
    if not result.value.is_folder:
        raise BootstrapError("configured root_id does not identify a folder")
    return result.value


def bootstrap_tree(
    backend: DriveBackend,
    *,
    root_id: str | None,
    blueprint_path: Path | None = None,
) -> BootstrapReport:
    """Create/reuse the static TB4 tree inside one explicitly selected root."""

    _verify_explicit_root(backend, root_id)
    assert root_id is not None
    blueprint = _load_blueprint(blueprint_path)
    root_spec = blueprint["root"]

    entries: dict[str, str] = {}
    created_count = 0
    reused_count = 0

    def remember(logical_ref: str, metadata: ObjectMetadata, created: bool) -> None:
        nonlocal created_count, reused_count
        entries[logical_ref] = metadata.object_id
        if created:
            created_count += 1
        else:
            reused_count += 1

    for child_name, child_spec in root_spec["children"].items():
        kind = child_spec["kind"]
        is_folder = kind == "folder"
        metadata, created = _ensure_child(
            backend,
            parent_id=root_id,
            name=child_name,
            is_folder=is_folder,
            initial_text=_initial_text(child_name, kind),
        )
        remember(child_name, metadata, created)

        if child_name == "DOG_HOUSE":
            for dog_name, dog_spec in child_spec["children"].items():
                dog_filename = dog_spec.get("initial_name", dog_name)
                dog_meta, dog_created = _ensure_child(
                    backend,
                    parent_id=metadata.object_id,
                    name=dog_filename,
                    is_folder=False,
                    initial_text="{}\n",
                )
                logical_object = dog_spec.get("logical_object", dog_name)
                remember(
                    f"DOG_HOUSE.{logical_object}",
                    dog_meta,
                    dog_created,
                )

    missing = sorted(GLOBAL_REFERENCES - set(entries))
    if missing:
        raise BootstrapError(
            f"blueprint/bootstrap mapping omitted required references: {missing}"
        )

    genesis_id = entries["GENESIS"]
    genesis_meta, genesis_created = _ensure_child(
        backend,
        parent_id=genesis_id,
        name="GENESIS_INFO",
        is_folder=False,
        initial_text=canonical_json_text(
            {
                "schema_version": int(blueprint["schema_version"]),
                "protocol_major": int(blueprint["protocol_major"]),
                "tree_blueprint": "protocol/tree-blueprint.yaml",
                "root_repair_policy": root_spec["repair_policy"],
            }
        ),
    )
    if genesis_created:
        created_count += 1
    else:
        reused_count += 1

    park_map = ParkMap(
        schema_version=1,
        protocol_major=int(blueprint["protocol_major"]),
        map_generation=0,
        root_id=root_id,
        devices={},
        entries=entries,
    )
    park_map_text = canonical_json_text(park_map.to_dict())
    map_id = park_map.lookup("PARK_MAP")

    current_map = backend.read_text(map_id)
    if current_map.ok and current_map.value is not None and current_map.value.text == park_map_text:
        write = None
    else:
        write = backend.replace_text(map_id, park_map_text)
        if not write.ok and write.outcome is not BackendOutcome.AMBIGUOUS:
            raise BootstrapError(
                f"failed to write PARK_MAP: {write.outcome.value}: {write.message or ''}"
            )

    readback = backend.read_text(map_id)
    if not readback.ok or readback.value is None:
        raise BootstrapError("PARK_MAP write could not be read back")
    try:
        observed_map = ParkMap.from_dict(json.loads(readback.value.text))
    except (ValueError, json.JSONDecodeError) as exc:
        raise BootstrapError(f"PARK_MAP readback invalid: {exc}") from exc
    if observed_map != park_map:
        raise BootstrapError("PARK_MAP readback does not match generated map")

    return BootstrapReport(
        root_id=root_id,
        park_map=park_map,
        created_count=created_count,
        reused_count=reused_count,
    )


def _initial_text(name: str, kind: str) -> str:
    if kind == "folder":
        return ""
    if name == "START_HERE":
        return (
            "TB4 persistent control tree. Read the public repository "
            "docs/START_HERE.md for protocol documentation.\n"
        )
    return "{}\n"
