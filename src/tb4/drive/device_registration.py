from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from tb4.core.models import DeviceId
from tb4.core.schemas import canonical_json_text, load_schema_store
from tb4.drive.backend import DriveBackend, ObjectMetadata
from tb4.drive.errors import BackendOutcome
from tb4.drive.park_map import (
    DeviceRegistration,
    ParkMap,
    ParkMapConflict,
)


class DeviceRegistrationError(RuntimeError):
    pass


class DeviceRegistrationConflict(DeviceRegistrationError):
    pass


class RegistrationOutcome(StrEnum):
    CREATED = "CREATED"
    RESUMED = "RESUMED"
    ALREADY_REGISTERED = "ALREADY_REGISTERED"


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    device_id: str
    device_key: str
    hostname: str | None
    os_family: str
    wake_on_lan: bool
    ssh_bootstrap: bool
    fetcher_ephemeral: bool = True
    inline_commands: bool = True
    script_artifacts: bool = True

    def dog_tag_body(self) -> dict[str, object]:
        body = {
            "schema_version": 1,
            "protocol_major": 1,
            "device_id": self.device_id,
            "hostname": self.hostname,
            "os_family": self.os_family.upper(),
            "capabilities": {
                "wake_on_lan": self.wake_on_lan,
                "ssh_bootstrap": self.ssh_bootstrap,
                "fetcher_ephemeral": self.fetcher_ephemeral,
                "inline_commands": self.inline_commands,
                "script_artifacts": self.script_artifacts,
            },
        }
        load_schema_store().validate("dog-tag.schema.json", body)
        return body


@dataclass(frozen=True, slots=True)
class DeviceRegistrationReport:
    outcome: RegistrationOutcome
    park_map: ParkMap
    created_count: int
    reused_count: int


@dataclass(slots=True)
class DeviceRegistrar:
    """Registration-only creator for one deterministic BALL_PARK device tree.

    Listing is deliberately confined to registration/recovery. Once PARK_MAP is
    persisted, normal runtime must address these objects by stable object ID.
    """

    backend: DriveBackend

    def register(
        self,
        park_map: ParkMap,
        profile: DeviceProfile,
    ) -> DeviceRegistrationReport:
        DeviceId(profile.device_id)
        DeviceRegistration(DeviceId(profile.device_id), profile.device_key)
        dog_tag_text = canonical_json_text(profile.dog_tag_body())

        if profile.device_id in park_map.devices:
            if park_map.device_key(profile.device_id) != profile.device_key:
                raise DeviceRegistrationConflict(
                    "registered device_id already has a different device_key"
                )
            self._verify_existing_registration(park_map, profile, dog_tag_text)
            return DeviceRegistrationReport(
                RegistrationOutcome.ALREADY_REGISTERED,
                park_map,
                created_count=0,
                reused_count=12,
            )

        ball_park_id = park_map.lookup("BALL_PARK")
        created_count = 0
        reused_count = 0

        def ensure(
            parent_id: str,
            name: str,
            *,
            folder: bool,
            text: str = "{}\n",
        ) -> ObjectMetadata:
            nonlocal created_count, reused_count
            item, created = self._ensure_child(
                parent_id,
                name,
                folder=folder,
                text=text,
            )
            if created:
                created_count += 1
            else:
                reused_count += 1
            return item

        root = ensure(ball_park_id, profile.device_key, folder=True)
        dog_tag = ensure(root.object_id, "DOG_TAG", folder=False, text=dog_tag_text)
        dog_sniff = ensure(root.object_id, "DOG_SNIFF", folder=False)
        dog_pulse = ensure(root.object_id, "DOG_PULSE", folder=False)
        leash = ensure(root.object_id, "LEASH_CLEAR", folder=False)

        kennel = ensure(root.object_id, "KENNEL", folder=True)
        wake_bone = ensure(kennel.object_id, "WAKE_BONE_READY", folder=False)

        playground = ensure(root.object_id, "PLAYGROUND", folder=True)
        fetch_ball = ensure(playground.object_id, "FETCH_BALL_READY", folder=False)
        stop_ball = ensure(playground.object_id, "STOP_BALL_READY", folder=False)

        toy_box = ensure(root.object_id, "TOY_BOX", folder=True)
        boneyard = ensure(root.object_id, "BONEYARD", folder=True)

        references = {
            ParkMap.device_ref(profile.device_id, "ROOT"): root.object_id,
            ParkMap.device_ref(profile.device_id, "DOG_TAG"): dog_tag.object_id,
            ParkMap.device_ref(profile.device_id, "DOG_SNIFF"): dog_sniff.object_id,
            ParkMap.device_ref(profile.device_id, "DOG_PULSE"): dog_pulse.object_id,
            ParkMap.device_ref(profile.device_id, "TARGET_LEASH"): leash.object_id,
            ParkMap.device_ref(profile.device_id, "KENNEL"): kennel.object_id,
            ParkMap.device_ref(profile.device_id, "KENNEL.WAKE_BONE"): wake_bone.object_id,
            ParkMap.device_ref(profile.device_id, "PLAYGROUND"): playground.object_id,
            ParkMap.device_ref(profile.device_id, "PLAYGROUND.FETCH_BALL"): fetch_ball.object_id,
            ParkMap.device_ref(profile.device_id, "PLAYGROUND.STOP_BALL"): stop_ball.object_id,
            ParkMap.device_ref(profile.device_id, "TOY_BOX"): toy_box.object_id,
            ParkMap.device_ref(profile.device_id, "BONEYARD"): boneyard.object_id,
        }

        try:
            updated = park_map.register_device(
                DeviceRegistration(DeviceId(profile.device_id), profile.device_key),
                references,
            )
        except ParkMapConflict as exc:
            raise DeviceRegistrationConflict(str(exc)) from exc

        self._persist_map(park_map, updated)

        outcome = (
            RegistrationOutcome.CREATED
            if reused_count == 0
            else RegistrationOutcome.RESUMED
        )
        return DeviceRegistrationReport(
            outcome,
            updated,
            created_count=created_count,
            reused_count=reused_count,
        )

    def _verify_existing_registration(
        self,
        park_map: ParkMap,
        profile: DeviceProfile,
        dog_tag_text: str,
    ) -> None:
        for suffix in (
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
        ):
            object_id = park_map.lookup_device(profile.device_id, suffix)
            metadata = self.backend.get_metadata(object_id)
            if not metadata.ok or metadata.value is None:
                raise DeviceRegistrationConflict(
                    f"registered reference {suffix} is not reachable"
                )

        tag_id = park_map.lookup_device(profile.device_id, "DOG_TAG")
        tag = self.backend.read_text(tag_id)
        if not tag.ok or tag.value is None:
            raise DeviceRegistrationConflict("registered DOG_TAG is unreadable")
        try:
            observed = json.loads(tag.value.text)
            expected = json.loads(dog_tag_text)
        except json.JSONDecodeError as exc:
            raise DeviceRegistrationConflict("registered DOG_TAG is invalid JSON") from exc
        if observed != expected:
            raise DeviceRegistrationConflict(
                "registered DOG_TAG does not match requested profile; update identity/capability data explicitly"
            )

    def _ensure_child(
        self,
        parent_id: str,
        name: str,
        *,
        folder: bool,
        text: str,
    ) -> tuple[ObjectMetadata, bool]:
        listing = self.backend.list_children(parent_id)
        if not listing.ok or listing.value is None:
            raise DeviceRegistrationError(
                f"cannot enumerate verified registration parent: {listing.outcome.value}"
            )
        matches = [item for item in listing.value if item.name == name]
        if len(matches) > 1:
            raise DeviceRegistrationConflict(
                f"ambiguous registration object {name!r}: {len(matches)} matches"
            )
        if matches:
            match = matches[0]
            if match.is_folder != folder:
                raise DeviceRegistrationConflict(
                    f"registration object {name!r} has wrong kind"
                )
            return match, False

        result = (
            self.backend.create_folder(parent_id, name)
            if folder
            else self.backend.create_text(parent_id, name, text)
        )
        if result.ok and result.value is not None:
            return result.value.metadata, True

        if result.outcome is BackendOutcome.AMBIGUOUS:
            listing = self.backend.list_children(parent_id)
            if not listing.ok or listing.value is None:
                raise DeviceRegistrationError(
                    f"ambiguous create for {name!r} could not be reconciled"
                )
            matches = [item for item in listing.value if item.name == name]
            if len(matches) == 1 and matches[0].is_folder == folder:
                return matches[0], True
            if len(matches) > 1:
                raise DeviceRegistrationConflict(
                    f"ambiguous create produced duplicate {name!r}"
                )
        raise DeviceRegistrationError(
            f"failed to create registration object {name!r}: {result.outcome.value}"
        )

    def _persist_map(self, old_map: ParkMap, new_map: ParkMap) -> None:
        map_id = old_map.lookup("PARK_MAP")
        metadata = self.backend.get_metadata(map_id)
        if not metadata.ok or metadata.value is None:
            raise DeviceRegistrationError("PARK_MAP metadata is unavailable")

        body = canonical_json_text(new_map.to_dict())
        write = self.backend.replace_text(
            map_id,
            body,
            expected_version_token=metadata.value.version_token,
        )
        if not write.ok and write.outcome is not BackendOutcome.AMBIGUOUS:
            raise DeviceRegistrationError(
                f"PARK_MAP update failed: {write.outcome.value}"
            )

        readback = self.backend.read_text(map_id)
        if not readback.ok or readback.value is None:
            raise DeviceRegistrationError("PARK_MAP update could not be read back")
        try:
            observed = ParkMap.from_dict(json.loads(readback.value.text))
        except (ValueError, json.JSONDecodeError) as exc:
            raise DeviceRegistrationError("PARK_MAP readback is invalid") from exc
        if observed != new_map:
            raise DeviceRegistrationError("PARK_MAP readback does not match registration")
