from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Mapping

from tb4.core.models import DeviceId


GLOBAL_REFERENCES = frozenset(
    {
        "START_HERE",
        "PARK_MAP",
        "GENESIS",
        "SETTINGS",
        "DOG_HOUSE",
        "DOG_HOUSE.DOG_TAG",
        "DOG_HOUSE.DOG_PULSE",
        "DOG_HOUSE.WATCHDOG_MODE",
        "DOG_HOUSE.WATCHDOG_FAULT",
        "BALL_PARK",
        "STRAY_YARD",
        "DOG_POUND",
    }
)

DEVICE_REFERENCE_SUFFIXES = frozenset(
    {
        "ROOT",
        "DOG_TAG",
        "DOG_SNIFF",
        "DOG_PULSE",
        "TARGET_LEASH",
        "KENNEL",
        "KENNEL.WAKE_BONE",
        "PLAYGROUND",
        "PLAYGROUND.FETCH_BALL",
        "PLAYGROUND.STOP_BALL",
        "TOY_BOX",
        "BONEYARD",
    }
)


class ParkMapError(ValueError):
    pass


class MissingParkReference(ParkMapError):
    pass


class DuplicateParkObjectId(ParkMapError):
    pass


class ParkMapVersionError(ParkMapError):
    pass


class ParkMapConflict(ParkMapError):
    pass


@dataclass(frozen=True, slots=True)
class DeviceRegistration:
    device_id: DeviceId
    device_key: str

    def __post_init__(self) -> None:
        if not self.device_key:
            raise ValueError("device_key must not be empty")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
        if any(char not in allowed for char in self.device_key):
            raise ValueError("device_key contains invalid characters")
        if len(self.device_key) > 128:
            raise ValueError("device_key is too long")


@dataclass(frozen=True, slots=True)
class ParkMap:
    schema_version: int
    protocol_major: int
    map_generation: int
    root_id: str
    devices: Mapping[str, DeviceRegistration]
    entries: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ParkMapVersionError(f"unsupported PARK_MAP schema_version {self.schema_version}")
        if self.protocol_major != 1:
            raise ParkMapVersionError(f"unsupported PARK_MAP protocol_major {self.protocol_major}")
        if self.map_generation < 0:
            raise ParkMapError("map_generation must be non-negative")
        if not self.root_id:
            raise ParkMapError("root_id must not be empty")

        devices = dict(self.devices)
        entries = dict(self.entries)
        object.__setattr__(self, "devices", MappingProxyType(devices))
        object.__setattr__(self, "entries", MappingProxyType(entries))

        self._validate_required_references()
        self._validate_unique_object_ids()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ParkMap":
        raw_devices = data.get("devices")
        raw_entries = data.get("entries")
        if not isinstance(raw_devices, Mapping):
            raise ParkMapError("devices must be an object")
        if not isinstance(raw_entries, Mapping):
            raise ParkMapError("entries must be an object")

        devices = {
            str(device_id): DeviceRegistration(
                DeviceId(str(device_id)),
                str(device_data["device_key"]),
            )
            for device_id, device_data in raw_devices.items()
        }
        entries = {str(key): str(value) for key, value in raw_entries.items()}
        return cls(
            schema_version=int(data["schema_version"]),
            protocol_major=int(data["protocol_major"]),
            map_generation=int(data["map_generation"]),
            root_id=str(data["root_id"]),
            devices=devices,
            entries=entries,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "protocol_major": self.protocol_major,
            "map_generation": self.map_generation,
            "root_id": self.root_id,
            "devices": {
                device_id: {"device_key": registration.device_key}
                for device_id, registration in sorted(self.devices.items())
            },
            "entries": dict(sorted(self.entries.items())),
        }

    @staticmethod
    def device_ref(device_id: DeviceId | str, suffix: str) -> str:
        device = device_id.value if isinstance(device_id, DeviceId) else DeviceId(str(device_id)).value
        if suffix not in DEVICE_REFERENCE_SUFFIXES:
            raise ParkMapError(f"unknown canonical device reference suffix {suffix!r}")
        return f"DEVICE.{device}.{suffix}"

    def lookup(self, logical_ref: str) -> str:
        try:
            return self.entries[logical_ref]
        except KeyError as exc:
            raise MissingParkReference(logical_ref) from exc

    def lookup_device(self, device_id: DeviceId | str, suffix: str) -> str:
        device = device_id.value if isinstance(device_id, DeviceId) else DeviceId(str(device_id)).value
        if device not in self.devices:
            raise MissingParkReference(f"unregistered device {device!r}")
        return self.lookup(self.device_ref(device, suffix))

    def device_key(self, device_id: DeviceId | str) -> str:
        device = device_id.value if isinstance(device_id, DeviceId) else DeviceId(str(device_id)).value
        try:
            return self.devices[device].device_key
        except KeyError as exc:
            raise MissingParkReference(f"unregistered device {device!r}") from exc

    def replace_reference(
        self,
        logical_ref: str,
        new_object_id: str,
        *,
        expected_old_object_id: str,
    ) -> "ParkMap":
        if not new_object_id:
            raise ParkMapError("new_object_id must not be empty")

        current = self.lookup(logical_ref)
        if current != expected_old_object_id:
            raise ParkMapConflict(
                f"{logical_ref} expected {expected_old_object_id!r}, observed {current!r}"
            )

        if new_object_id != current:
            for other_ref, object_id in self.entries.items():
                if other_ref != logical_ref and object_id == new_object_id:
                    raise DuplicateParkObjectId(
                        f"object ID {new_object_id!r} already belongs to {other_ref}"
                    )

        updated = dict(self.entries)
        updated[logical_ref] = new_object_id
        return ParkMap(
            schema_version=self.schema_version,
            protocol_major=self.protocol_major,
            map_generation=self.map_generation + 1,
            root_id=self.root_id,
            devices=self.devices,
            entries=updated,
        )

    def register_device(
        self,
        registration: DeviceRegistration,
        references: Mapping[str, str],
    ) -> "ParkMap":
        device_id = registration.device_id.value
        if device_id in self.devices:
            raise ParkMapConflict(f"device {device_id!r} is already registered")

        expected_refs = {
            self.device_ref(device_id, suffix)
            for suffix in DEVICE_REFERENCE_SUFFIXES
        }
        if set(references) != expected_refs:
            missing = sorted(expected_refs - set(references))
            extra = sorted(set(references) - expected_refs)
            raise ParkMapError(f"device reference set mismatch; missing={missing}, extra={extra}")

        used_ids = set(self.entries.values()) | {self.root_id}
        duplicate_ids = sorted(set(references.values()) & used_ids)
        if duplicate_ids:
            raise DuplicateParkObjectId(
                f"new device references reuse existing object ID(s): {duplicate_ids}"
            )
        if len(set(references.values())) != len(references):
            raise DuplicateParkObjectId("new device reference set contains duplicate object IDs")

        devices = dict(self.devices)
        devices[device_id] = registration
        entries = dict(self.entries)
        entries.update(references)
        return ParkMap(
            schema_version=self.schema_version,
            protocol_major=self.protocol_major,
            map_generation=self.map_generation + 1,
            root_id=self.root_id,
            devices=devices,
            entries=entries,
        )

    def _validate_required_references(self) -> None:
        missing_globals = sorted(GLOBAL_REFERENCES - set(self.entries))
        if missing_globals:
            raise MissingParkReference(f"missing global reference(s): {missing_globals}")

        for device_id in self.devices:
            for suffix in DEVICE_REFERENCE_SUFFIXES:
                ref = self.device_ref(device_id, suffix)
                if ref not in self.entries:
                    raise MissingParkReference(ref)

        for ref in self.entries:
            if ref in GLOBAL_REFERENCES:
                continue
            if not ref.startswith("DEVICE."):
                raise ParkMapError(f"unknown logical reference {ref!r}")

            parts = ref.split(".")
            if len(parts) < 3:
                raise ParkMapError(f"malformed device logical reference {ref!r}")
            device_id = parts[1]
            suffix = ".".join(parts[2:])
            if device_id not in self.devices:
                raise ParkMapError(f"reference belongs to unregistered device {device_id!r}")
            if suffix not in DEVICE_REFERENCE_SUFFIXES:
                raise ParkMapError(f"unknown device logical reference suffix {suffix!r}")

    def _validate_unique_object_ids(self) -> None:
        owner_by_id: dict[str, str] = {self.root_id: "ROOT"}
        for logical_ref, object_id in self.entries.items():
            if not object_id:
                raise ParkMapError(f"{logical_ref} has empty object ID")
            previous = owner_by_id.get(object_id)
            if previous is not None:
                raise DuplicateParkObjectId(
                    f"object ID {object_id!r} is mapped by both {previous} and {logical_ref}"
                )
            owner_by_id[object_id] = logical_ref
