from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

import yaml

from tb4.core.protocol_names import LogicalObject, state_filename
from tb4.core.state_machine import StateMachineRegistry, load_state_machines

from .backend import DriveBackend, ObjectMetadata
from .errors import BackendOutcome
from .park_map import ParkMap


class TreeIssueKind(StrEnum):
    ROOT_UNREACHABLE = "ROOT_UNREACHABLE"
    ROOT_WRONG_KIND = "ROOT_WRONG_KIND"
    PARK_MAP_CONFLICT = "PARK_MAP_CONFLICT"
    CANONICAL_ID_MISSING = "CANONICAL_ID_MISSING"
    CANONICAL_WRONG_PARENT = "CANONICAL_WRONG_PARENT"
    CANONICAL_WRONG_KIND = "CANONICAL_WRONG_KIND"
    CANONICAL_NAME_INVALID = "CANONICAL_NAME_INVALID"
    DUPLICATE_CANONICAL = "DUPLICATE_CANONICAL"
    UNKNOWN_CHILD = "UNKNOWN_CHILD"


@dataclass(frozen=True, slots=True)
class ExpectedChild:
    logical_ref: str
    parent_ref: str
    expected_is_folder: bool
    allowed_names: tuple[str, ...]
    initial_name: str
    repair_policy: str
    stateful: bool = False


@dataclass(frozen=True, slots=True)
class TreeIssue:
    kind: TreeIssueKind
    logical_ref: str | None
    object_id: str | None
    parent_id: str | None
    expected_parent_id: str | None
    expected_is_folder: bool | None
    allowed_names: tuple[str, ...] = ()
    initial_name: str | None = None
    repair_policy: str | None = None
    candidate_ids: tuple[str, ...] = ()
    stateful: bool = False
    message: str | None = None


@dataclass(frozen=True, slots=True)
class TreeAuditReport:
    root_id: str
    issues: tuple[TreeIssue, ...]
    scanned_parent_count: int

    @property
    def clean(self) -> bool:
        return not self.issues

    @property
    def blocking(self) -> bool:
        return any(
            issue.kind
            in {
                TreeIssueKind.ROOT_UNREACHABLE,
                TreeIssueKind.ROOT_WRONG_KIND,
                TreeIssueKind.PARK_MAP_CONFLICT,
            }
            or issue.logical_ref == "PARK_MAP"
            for issue in self.issues
        )


def canonical_blueprint_path() -> Path:
    return Path(__file__).resolve().parents[3] / "protocol" / "tree-blueprint.yaml"


def load_tree_blueprint(path: Path | None = None) -> dict[str, Any]:
    resolved = canonical_blueprint_path() if path is None else path.resolve()
    return yaml.safe_load(resolved.read_text(encoding="utf-8"))


def _allowed_state_names(
    logical_object: str,
    registry: StateMachineRegistry,
) -> tuple[str, ...]:
    machine = registry.machine(logical_object)
    if machine is None:
        raise ValueError(f"missing state machine for {logical_object}")
    enum_value = LogicalObject(logical_object)
    return tuple(sorted(state_filename(enum_value, state) for state in machine.states))


def build_expectations(
    blueprint: dict[str, Any],
    park_map: ParkMap,
    *,
    registry: StateMachineRegistry | None = None,
) -> tuple[ExpectedChild, ...]:
    active_registry = registry if registry is not None else load_state_machines()
    expectations: list[ExpectedChild] = []
    root = blueprint["root"]

    for child_name, spec in root["children"].items():
        expectations.append(
            ExpectedChild(
                logical_ref=child_name,
                parent_ref="ROOT",
                expected_is_folder=spec["kind"] == "folder",
                allowed_names=(child_name,),
                initial_name=child_name,
                repair_policy=spec["repair_policy"],
            )
        )

    dog_house = root["children"]["DOG_HOUSE"]
    for child_name, spec in dog_house["children"].items():
        logical = spec.get("logical_object", child_name)
        logical_ref = f"DOG_HOUSE.{logical}"
        if spec["kind"] == "stateful_object":
            names = _allowed_state_names(logical, active_registry)
            initial_name = spec["initial_name"]
            stateful = True
        else:
            names = (child_name,)
            initial_name = child_name
            stateful = False
        expectations.append(
            ExpectedChild(
                logical_ref=logical_ref,
                parent_ref="DOG_HOUSE",
                expected_is_folder=False,
                allowed_names=names,
                initial_name=initial_name,
                repair_policy=spec["repair_policy"],
                stateful=stateful,
            )
        )

    device_tree = blueprint["subtrees"]["DEVICE_TREE"]
    for device_id, registration in park_map.devices.items():
        root_ref = park_map.device_ref(device_id, "ROOT")
        expectations.append(
            ExpectedChild(
                logical_ref=root_ref,
                parent_ref="BALL_PARK",
                expected_is_folder=True,
                allowed_names=(registration.device_key,),
                initial_name=registration.device_key,
                repair_policy="never_auto_recreate",
            )
        )

        for child_name, spec in device_tree["children"].items():
            suffix = spec.get("logical_object", child_name)
            child_ref = park_map.device_ref(device_id, suffix)
            if spec["kind"] == "stateful_object":
                logical = spec["logical_object"]
                names = _allowed_state_names(logical, active_registry)
                initial_name = spec["initial_name"]
                stateful = True
            else:
                names = (child_name,)
                initial_name = child_name
                stateful = False
            expectations.append(
                ExpectedChild(
                    logical_ref=child_ref,
                    parent_ref=root_ref,
                    expected_is_folder=spec["kind"] == "folder",
                    allowed_names=names,
                    initial_name=initial_name,
                    repair_policy=spec["repair_policy"],
                    stateful=stateful,
                )
            )

            if child_name in {"KENNEL", "PLAYGROUND"}:
                parent_ref = child_ref
                for nested_name, nested_spec in spec["children"].items():
                    nested_suffix = nested_spec.get("logical_object", nested_name)
                    nested_ref = park_map.device_ref(device_id, nested_suffix)
                    if nested_spec["kind"] == "stateful_object":
                        logical = nested_spec["logical_object"]
                        names = _allowed_state_names(logical, active_registry)
                        initial_name = nested_spec["initial_name"]
                        stateful = True
                    else:
                        names = (nested_name,)
                        initial_name = nested_name
                        stateful = False
                    expectations.append(
                        ExpectedChild(
                            logical_ref=nested_ref,
                            parent_ref=parent_ref,
                            expected_is_folder=nested_spec["kind"] == "folder",
                            allowed_names=names,
                            initial_name=initial_name,
                            repair_policy=nested_spec["repair_policy"],
                            stateful=stateful,
                        )
                    )

    return tuple(expectations)


class TreeAuditor:
    """Maintenance-only tree inspection.

    This class intentionally uses list_children. Normal TB4 control paths must
    continue to use PARK_MAP stable object IDs instead of directory scans.
    """

    def __init__(
        self,
        backend: DriveBackend,
        *,
        blueprint_path: Path | None = None,
        registry: StateMachineRegistry | None = None,
    ) -> None:
        self.backend = backend
        self.blueprint = load_tree_blueprint(blueprint_path)
        self.registry = registry if registry is not None else load_state_machines()

    def audit(self, *, root_id: str, park_map: ParkMap) -> TreeAuditReport:
        issues: list[TreeIssue] = []
        scanned = 0

        root_result = self.backend.get_metadata(root_id)
        if not root_result.ok:
            issues.append(
                TreeIssue(
                    TreeIssueKind.ROOT_UNREACHABLE,
                    None,
                    root_id,
                    None,
                    None,
                    True,
                    message=root_result.outcome.value,
                )
            )
            return TreeAuditReport(root_id, tuple(issues), scanned)

        root_meta = root_result.value
        assert root_meta is not None
        if not root_meta.is_folder:
            issues.append(
                TreeIssue(
                    TreeIssueKind.ROOT_WRONG_KIND,
                    None,
                    root_id,
                    None,
                    None,
                    True,
                )
            )
            return TreeAuditReport(root_id, tuple(issues), scanned)

        if park_map.root_id != root_id:
            issues.append(
                TreeIssue(
                    TreeIssueKind.PARK_MAP_CONFLICT,
                    "PARK_MAP",
                    park_map.entries.get("PARK_MAP"),
                    None,
                    root_id,
                    False,
                    message="PARK_MAP root_id does not match configured root",
                )
            )
            return TreeAuditReport(root_id, tuple(issues), scanned)

        expectations = build_expectations(
            self.blueprint,
            park_map,
            registry=self.registry,
        )
        by_parent: dict[str, list[ExpectedChild]] = {}
        for expected in expectations:
            by_parent.setdefault(expected.parent_ref, []).append(expected)

        for parent_ref, children_specs in by_parent.items():
            parent_id = root_id if parent_ref == "ROOT" else park_map.lookup(parent_ref)
            parent_result = self.backend.get_metadata(parent_id)
            if not parent_result.ok or parent_result.value is None:
                for expected in children_specs:
                    issues.append(
                        self._issue(
                            TreeIssueKind.CANONICAL_ID_MISSING,
                            expected,
                            park_map.entries.get(expected.logical_ref),
                            parent_id,
                            (),
                            "expected parent is unavailable",
                        )
                    )
                continue
            if not parent_result.value.is_folder:
                for expected in children_specs:
                    issues.append(
                        self._issue(
                            TreeIssueKind.CANONICAL_WRONG_PARENT,
                            expected,
                            park_map.entries.get(expected.logical_ref),
                            parent_id,
                            (),
                            "expected parent is not a folder",
                        )
                    )
                continue

            listed = self.backend.list_children(parent_id)
            scanned += 1
            if not listed.ok or listed.value is None:
                issues.append(
                    TreeIssue(
                        TreeIssueKind.PARK_MAP_CONFLICT,
                        parent_ref,
                        parent_id,
                        parent_id,
                        parent_id,
                        True,
                        message=f"cannot enumerate audit parent: {listed.outcome.value}",
                    )
                )
                continue
            children = tuple(listed.value)

            canonical_ids: set[str] = set()
            duplicate_ids: set[str] = set()

            for expected in children_specs:
                canonical_id = park_map.entries.get(expected.logical_ref)
                if canonical_id is None:
                    issues.append(
                        self._issue(
                            TreeIssueKind.PARK_MAP_CONFLICT,
                            expected,
                            None,
                            parent_id,
                            (),
                            "PARK_MAP omitted canonical reference",
                        )
                    )
                    continue
                canonical_ids.add(canonical_id)

                matching = tuple(
                    item
                    for item in children
                    if item.name in expected.allowed_names
                )
                matching_ids = tuple(item.object_id for item in matching)

                canonical = self.backend.get_metadata(canonical_id)
                if canonical.outcome is BackendOutcome.NOT_FOUND:
                    issues.append(
                        self._issue(
                            TreeIssueKind.CANONICAL_ID_MISSING,
                            expected,
                            canonical_id,
                            parent_id,
                            matching_ids,
                            "PARK_MAP canonical object ID is missing",
                        )
                    )
                elif not canonical.ok or canonical.value is None:
                    issues.append(
                        self._issue(
                            TreeIssueKind.PARK_MAP_CONFLICT,
                            expected,
                            canonical_id,
                            parent_id,
                            matching_ids,
                            canonical.outcome.value,
                        )
                    )
                else:
                    meta = canonical.value
                    if meta.parent_ids != (parent_id,):
                        issues.append(
                            self._issue(
                                TreeIssueKind.CANONICAL_WRONG_PARENT,
                                expected,
                                canonical_id,
                                parent_id,
                                matching_ids,
                                f"canonical parent is {meta.parent_ids!r}",
                            )
                        )
                    if meta.is_folder != expected.expected_is_folder:
                        issues.append(
                            self._issue(
                                TreeIssueKind.CANONICAL_WRONG_KIND,
                                expected,
                                canonical_id,
                                parent_id,
                                matching_ids,
                                "canonical object has wrong folder/file kind",
                            )
                        )
                    if meta.name not in expected.allowed_names:
                        issues.append(
                            self._issue(
                                TreeIssueKind.CANONICAL_NAME_INVALID,
                                expected,
                                canonical_id,
                                parent_id,
                                matching_ids,
                                f"canonical name {meta.name!r} is not valid",
                            )
                        )

                extras = tuple(
                    item.object_id
                    for item in matching
                    if item.object_id != canonical_id
                )
                if extras:
                    duplicate_ids.update(extras)
                    issues.append(
                        self._issue(
                            TreeIssueKind.DUPLICATE_CANONICAL,
                            expected,
                            canonical_id,
                            parent_id,
                            extras,
                            "additional object uses a canonical active name",
                        )
                    )

            known_noncanonical = duplicate_ids
            allowed_dynamic_parent = parent_ref in {
                "STRAY_YARD",
                "DOG_POUND",
            } or parent_ref.endswith(".TOY_BOX") or parent_ref.endswith(".BONEYARD")
            if not allowed_dynamic_parent:
                for child in children:
                    if child.object_id in canonical_ids or child.object_id in known_noncanonical:
                        continue
                    issues.append(
                        TreeIssue(
                            TreeIssueKind.UNKNOWN_CHILD,
                            None,
                            child.object_id,
                            parent_id,
                            parent_id,
                            child.is_folder,
                            message=f"unknown child {child.name!r} in audited control folder",
                        )
                    )

        return TreeAuditReport(root_id, tuple(issues), scanned)

    @staticmethod
    def _issue(
        kind: TreeIssueKind,
        expected: ExpectedChild,
        object_id: str | None,
        parent_id: str,
        candidate_ids: Iterable[str],
        message: str,
    ) -> TreeIssue:
        return TreeIssue(
            kind=kind,
            logical_ref=expected.logical_ref,
            object_id=object_id,
            parent_id=parent_id,
            expected_parent_id=parent_id,
            expected_is_folder=expected.expected_is_folder,
            allowed_names=expected.allowed_names,
            initial_name=expected.initial_name,
            repair_policy=expected.repair_policy,
            candidate_ids=tuple(candidate_ids),
            stateful=expected.stateful,
            message=message,
        )
