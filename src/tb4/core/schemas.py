from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class SchemaValidationError(ValueError):
    pass


class SchemaStore:
    def __init__(self, schema_dir: Path) -> None:
        self.schema_dir = schema_dir.resolve()
        self._schemas: dict[str, dict[str, Any]] = {}
        registry = Registry()

        for path in sorted(self.schema_dir.glob("*.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schema_id = schema.get("$id")
            if not isinstance(schema_id, str) or not schema_id:
                raise SchemaValidationError(f"{path.name} has no canonical $id")
            self._schemas[path.name] = schema
            registry = registry.with_resource(
                schema_id,
                Resource.from_contents(schema),
            )

        self._registry = registry

    def validator(self, schema_name: str) -> Draft202012Validator:
        try:
            schema = self._schemas[schema_name]
        except KeyError as exc:
            raise SchemaValidationError(f"unknown schema {schema_name!r}") from exc
        return Draft202012Validator(schema, registry=self._registry)

    def validate(self, schema_name: str, body: Mapping[str, Any]) -> None:
        errors = sorted(
            self.validator(schema_name).iter_errors(dict(body)),
            key=lambda error: list(error.absolute_path),
        )
        if not errors:
            return
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path)
        location = f" at {path}" if path else ""
        raise SchemaValidationError(
            f"{schema_name}{location}: {first.message}"
        )


def canonical_schema_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "protocol" / "schemas"


@lru_cache(maxsize=8)
def load_schema_store(path: str | Path | None = None) -> SchemaStore:
    resolved = canonical_schema_dir() if path is None else Path(path).resolve()
    return SchemaStore(resolved)


def canonical_json_text(body: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(body),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
