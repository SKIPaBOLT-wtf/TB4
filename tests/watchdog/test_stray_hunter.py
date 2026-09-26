from __future__ import annotations

import json
from dataclasses import dataclass

from tb4.core.retry import RetryPolicy
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.watchdog.stray_hunter import (
    DiscoveredDevice,
    StrayHunter,
    StrayOutcome,
)


@dataclass
class FakeClock:
    monotonic_value: float = 100.0
    epoch_value: int = 1_700_300_000

    def monotonic(self) -> float:
        return self.monotonic_value

    def epoch(self) -> int:
        value = self.epoch_value
        self.epoch_value += 1
        return value

    def sleep(self, seconds: float) -> None:
        self.monotonic_value += seconds


@dataclass
class MutableDiscovery:
    devices: tuple[DiscoveredDevice, ...]
    error: Exception | None = None

    def scan(self):
        if self.error is not None:
            raise self.error
        return self.devices


def make_hunter(devices: tuple[DiscoveredDevice, ...]):
    backend = InMemoryDriveBackend()
    yard = backend.create_folder(backend.root_id, "STRAY_YARD")
    assert yard.ok and yard.value is not None
    clock = FakeClock()
    discovery = MutableDiscovery(devices)
    hunter = StrayHunter(
        backend=backend,
        discovery=discovery,
        stray_yard_folder_id=yard.value.metadata.object_id,
        retry_policy=RetryPolicy((0.01, 0.02, 0.04), 3),
        epoch_now=clock.epoch,
        monotonic_now=clock.monotonic,
        sleeper=clock.sleep,
    )
    backend.reset_operation_counts()
    return backend, clock, discovery, hunter, yard.value.metadata.object_id


def device(*, address="192.0.2.20", stable="switch-port-17"):
    return DiscoveredDevice(
        addresses=(address,),
        mac_address="00:11:22:33:44:55",
        stable_hardware_id=stable,
        discovery_kind="ARP_SCAN",
    )


def card_body(backend: InMemoryDriveBackend, yard_id: str) -> tuple[str, dict]:
    yard = backend.list_children(yard_id)
    assert yard.ok and yard.value is not None
    folders = [item for item in yard.value if item.is_folder and item.name.startswith("stray-")]
    assert len(folders) == 1
    children = backend.list_children(folders[0].object_id)
    assert children.ok and children.value is not None
    cards = [item for item in children.value if item.name == "STRAY_CARD"]
    assert len(cards) == 1
    remote = backend.read_text(cards[0].object_id)
    assert remote.ok and remote.value is not None
    return folders[0].name, json.loads(remote.value.text)


def test_new_device_creates_deterministic_stray_folder_and_card() -> None:
    backend, _, _, hunter, yard_id = make_hunter((device(),))

    report = hunter.scan_once()

    assert report.results[0].outcome is StrayOutcome.CREATED
    name, body = card_body(backend, yard_id)
    assert name == report.results[0].stray_key
    assert name.startswith("stray-")
    assert len(name) == len("stray-") + 12
    assert body["first_seen"] == body["last_seen"]
    assert body["addresses"] == ["192.0.2.20"]


def test_repeated_unchanged_discovery_does_not_write_again() -> None:
    backend, _, _, hunter, _ = make_hunter((device(),))
    first = hunter.scan_once()
    assert first.results[0].outcome is StrayOutcome.CREATED
    writes_before = (
        backend.operation_counts.get("create_folder", 0),
        backend.operation_counts.get("create_text", 0),
        backend.operation_counts.get("replace_text", 0),
    )

    second = hunter.scan_once()

    assert second.results[0].outcome is StrayOutcome.UNCHANGED
    writes_after = (
        backend.operation_counts.get("create_folder", 0),
        backend.operation_counts.get("create_text", 0),
        backend.operation_counts.get("replace_text", 0),
    )
    assert writes_after == writes_before


def test_address_change_updates_same_stable_stray_identity() -> None:
    backend, _, discovery, hunter, yard_id = make_hunter((device(),))
    first = hunter.scan_once()
    key = first.results[0].stray_key

    discovery.devices = (device(address="192.0.2.99"),)
    second = hunter.scan_once()

    assert second.results[0].outcome is StrayOutcome.UPDATED
    assert second.results[0].stray_key == key
    name, body = card_body(backend, yard_id)
    assert name == key
    assert body["addresses"] == ["192.0.2.99"]
    assert body["last_seen"] > body["first_seen"]


def test_identity_without_hardware_uses_deterministic_address_fallback() -> None:
    unknown = DiscoveredDevice(
        addresses=("192.0.2.77",),
        discovery_kind="PING_SWEEP",
    )
    _, _, _, hunter, _ = make_hunter((unknown,))

    first = hunter.scan_once()
    second = hunter.scan_once()

    assert first.results[0].outcome is StrayOutcome.CREATED
    assert second.results[0].outcome is StrayOutcome.UNCHANGED
    assert first.results[0].stray_key == second.results[0].stray_key


def test_discovery_without_any_identity_is_not_published() -> None:
    backend, _, _, hunter, _ = make_hunter((DiscoveredDevice(),))

    report = hunter.scan_once()

    assert report.results[0].outcome is StrayOutcome.UNRESOLVED
    assert backend.operation_counts.get("create_folder", 0) == 0
    assert backend.operation_counts.get("create_text", 0) == 0


def test_discovery_backend_failure_is_reported_without_drive_write() -> None:
    backend, _, discovery, hunter, _ = make_hunter(())
    discovery.error = OSError("scan unavailable")
    backend.reset_operation_counts()

    report = hunter.scan_once()

    assert "OSError" in (report.backend_error or "")
    assert backend.operation_counts.get("create_folder", 0) == 0
    assert backend.operation_counts.get("create_text", 0) == 0
    assert backend.operation_counts.get("replace_text", 0) == 0


def test_stray_hunter_never_creates_ball_park_objects() -> None:
    backend, _, _, hunter, _ = make_hunter((device(),))

    hunter.scan_once()

    root = backend.list_children(backend.root_id)
    assert root.ok and root.value is not None
    assert {item.name for item in root.value} == {"STRAY_YARD"}


def test_duplicate_stray_folder_fails_closed() -> None:
    backend, _, _, hunter, yard_id = make_hunter((device(),))
    first = hunter.scan_once()
    key = first.results[0].stray_key
    assert key is not None
    duplicate = backend.create_folder(yard_id, key)
    assert duplicate.ok

    result = hunter.scan_once().results[0]

    assert result.outcome is StrayOutcome.FAILURE
    assert "duplicate" in (result.message or "").lower()
