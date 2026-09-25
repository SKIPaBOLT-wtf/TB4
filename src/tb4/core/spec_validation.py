from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class SpecError:
    file: str
    path: str
    message: str

    def format(self) -> str:
        location = self.file
        if self.path:
            location += f":{self.path}"
        return f"{location}: {self.message}"


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate mapping key {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=_UniqueKeyLoader)


def _load_json(path: Path) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate object key {key!r}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def _config_ref(config: dict[str, Any], ref: str) -> Any:
    value: Any = config
    for component in ref.split("."):
        if not isinstance(value, dict) or component not in value:
            raise KeyError(ref)
        value = value[component]
    return value


def _walk_refs(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        if set(value) == {"ref"} and isinstance(value["ref"], str):
            yield value["ref"]
        for child in value.values():
            yield from _walk_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_refs(child)


def _expected_filename(object_name: str, definition: dict[str, Any], state: str) -> str:
    filenames = definition.get("filenames")
    if isinstance(filenames, dict):
        return filenames[state]
    root = definition.get("root_name", object_name)
    return f"{root}_{state}"


def validate_protocol(root: Path) -> list[SpecError]:
    """Validate canonical TB4 specification files without modifying them."""

    root = root.resolve()
    errors: list[SpecError] = []

    paths = {
        "objects": root / "protocol" / "objects.yaml",
        "states": root / "protocol" / "state-machines.yaml",
        "tree": root / "protocol" / "tree-blueprint.yaml",
        "rules": root / "protocol" / "config-rules.yaml",
        "defaults": root / "config" / "defaults.toml",
    }

    loaded: dict[str, Any] = {}
    for name, path in paths.items():
        try:
            if path.suffix == ".yaml":
                loaded[name] = _load_yaml(path)
            elif path.suffix == ".toml":
                loaded[name] = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, yaml.YAMLError, tomllib.TOMLDecodeError) as exc:
            errors.append(SpecError(str(path.relative_to(root)), "", f"parse error: {exc}"))

    schema_dir = root / "protocol" / "schemas"
    schemas: dict[str, Any] = {}
    if not schema_dir.is_dir():
        errors.append(SpecError("protocol/schemas", "", "schema directory is missing"))
    else:
        for path in sorted(schema_dir.glob("*.json")):
            rel = str(path.relative_to(root))
            try:
                schema = _load_json(path)
                Draft202012Validator.check_schema(schema)
                schemas[path.name] = schema
            except (OSError, ValueError, json.JSONDecodeError, Exception) as exc:
                # jsonschema raises several public exception types; all are safe to report here.
                errors.append(SpecError(rel, "", f"invalid JSON Schema: {exc}"))

    if {"objects", "states"} <= loaded.keys():
        _validate_objects_and_states(loaded["objects"], loaded["states"], errors)

    if {"objects", "states", "tree"} <= loaded.keys():
        _validate_tree(loaded["objects"], loaded["states"], loaded["tree"], errors)

    if {"rules", "defaults"} <= loaded.keys():
        _validate_config_rules(loaded["rules"], loaded["defaults"], errors)

    _validate_required_schemas(schemas, errors)
    return errors


def _validate_objects_and_states(
    objects: dict[str, Any], states: dict[str, Any], errors: list[SpecError]
) -> None:
    roles = set(objects.get("roles", {}))
    stateful = objects.get("stateful_objects", {})
    machines = states.get("state_machines", {})

    for object_name, definition in stateful.items():
        if object_name not in machines:
            errors.append(
                SpecError("protocol/state-machines.yaml", f"state_machines.{object_name}",
                          "state machine is missing for registered stateful object")
            )
            continue
        registered = set(definition.get("states", definition.get("filenames", {})))
        machine_states = set(machines[object_name].get("states", {}))
        if registered != machine_states:
            errors.append(
                SpecError(
                    "protocol/objects.yaml",
                    f"stateful_objects.{object_name}.states",
                    f"registered states {sorted(registered)} do not match machine states {sorted(machine_states)}",
                )
            )

    for machine_name, machine in machines.items():
        if machine_name not in stateful:
            errors.append(
                SpecError("protocol/state-machines.yaml", f"state_machines.{machine_name}",
                          "state machine has no registered stateful object")
            )
            continue

        known_states = set(machine.get("states", {}))
        initial = machine.get("initial_state")
        if initial not in known_states:
            errors.append(
                SpecError("protocol/state-machines.yaml", f"state_machines.{machine_name}.initial_state",
                          f"unknown initial state {initial!r}")
            )

        for state_name, state_def in machine.get("states", {}).items():
            for writer in state_def.get("body_writers", []):
                if writer not in roles:
                    errors.append(
                        SpecError(
                            "protocol/state-machines.yaml",
                            f"state_machines.{machine_name}.states.{state_name}.body_writers",
                            f"unknown role {writer!r}",
                        )
                    )

        for index, transition in enumerate(machine.get("transitions", [])):
            path = f"state_machines.{machine_name}.transitions[{index}]"
            for edge_key in ("from", "to"):
                if transition.get(edge_key) not in known_states:
                    errors.append(
                        SpecError("protocol/state-machines.yaml", f"{path}.{edge_key}",
                                  f"unknown state {transition.get(edge_key)!r}")
                    )
            if transition.get("actor") not in roles:
                errors.append(
                    SpecError("protocol/state-machines.yaml", f"{path}.actor",
                              f"unknown role {transition.get('actor')!r}")
                )


def _validate_tree(
    objects: dict[str, Any],
    states: dict[str, Any],
    tree: dict[str, Any],
    errors: list[SpecError],
) -> None:
    fixed = set(objects.get("fixed_objects", {}))
    stateful = objects.get("stateful_objects", {})
    machines = states.get("state_machines", {})

    def walk(node: Any, path: str) -> None:
        if isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
            return
        if not isinstance(node, dict):
            return

        logical = node.get("logical_object")
        kind = node.get("kind")
        if logical:
            if kind == "fixed_object" and logical not in fixed:
                errors.append(SpecError("protocol/tree-blueprint.yaml", path + ".logical_object",
                                        f"unknown fixed object {logical!r}"))
            if kind == "stateful_object":
                if logical not in stateful:
                    errors.append(SpecError("protocol/tree-blueprint.yaml", path + ".logical_object",
                                            f"unknown stateful object {logical!r}"))
                else:
                    initial_name = node.get("initial_name")
                    initial_state = machines.get(logical, {}).get("initial_state")
                    if initial_name and initial_state:
                        expected = _expected_filename(logical, stateful[logical], initial_state)
                        if initial_name != expected:
                            errors.append(
                                SpecError("protocol/tree-blueprint.yaml", path + ".initial_name",
                                          f"{initial_name!r} does not match canonical initial filename {expected!r}")
                            )
        for key, child in node.items():
            if isinstance(child, (dict, list)):
                walk(child, f"{path}.{key}" if path else key)

    walk(tree, "")


def _validate_config_rules(
    rules: dict[str, Any], config: dict[str, Any], errors: list[SpecError]
) -> None:
    allowed_ops = {"gte", "lte", "mul", "add", "sum", "nondecreasing"}
    seen: set[str] = set()

    def walk_ops(value: Any, path: str) -> None:
        if isinstance(value, dict):
            op = value.get("op")
            if op is not None and op not in allowed_ops:
                errors.append(SpecError("protocol/config-rules.yaml", path + ".op",
                                        f"unknown rule operator {op!r}"))
            for key, child in value.items():
                walk_ops(child, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk_ops(child, f"{path}[{index}]")

    for index, rule in enumerate(rules.get("rules", [])):
        path = f"rules[{index}]"
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            errors.append(SpecError("protocol/config-rules.yaml", path + ".id", "missing rule ID"))
        elif rule_id in seen:
            errors.append(SpecError("protocol/config-rules.yaml", path + ".id",
                                    f"duplicate rule ID {rule_id!r}"))
        else:
            seen.add(rule_id)

        if rule.get("severity") not in {"FATAL", "WARNING"}:
            errors.append(SpecError("protocol/config-rules.yaml", path + ".severity",
                                    "severity must be FATAL or WARNING"))

        check = rule.get("check")
        if not isinstance(check, dict):
            errors.append(SpecError("protocol/config-rules.yaml", path + ".check", "missing check expression"))
            continue
        walk_ops(check, path + ".check")
        for ref in _walk_refs(check):
            try:
                _config_ref(config, ref)
            except KeyError:
                errors.append(SpecError("protocol/config-rules.yaml", path + ".check",
                                        f"unknown configuration reference {ref!r}"))


def _validate_required_schemas(
    schemas: dict[str, Any], errors: list[SpecError]
) -> None:
    required = {
        "control-envelope.schema.json",
        "fetch-ball.schema.json",
        "wake-bone.schema.json",
        "stop-ball.schema.json",
        "dog-tag.schema.json",
        "dog-pulse.schema.json",
        "dog-sniff.schema.json",
        "target-fault.schema.json",
    }
    for missing in sorted(required - schemas.keys()):
        errors.append(SpecError("protocol/schemas", missing, "required canonical schema is missing"))
