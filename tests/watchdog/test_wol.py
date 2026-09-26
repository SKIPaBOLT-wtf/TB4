from __future__ import annotations

from dataclasses import dataclass

from tb4.watchdog.wol import (
    BoneThrowOutcome,
    BoneThrower,
    WakeTarget,
    magic_packet,
)


@dataclass
class FakeSender:
    fail: Exception | None = None
    short_by: int = 0
    calls: list[tuple[bytes, str, int]] | None = None

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def send(self, payload: bytes, host: str, port: int) -> int:
        assert self.calls is not None
        self.calls.append((payload, host, port))
        if self.fail is not None:
            raise self.fail
        return len(payload) - self.short_by


def target(**overrides):
    values = {
        "wake_on_lan": True,
        "mac_address": "00:11:22:33:44:55",
        "broadcast_address": "192.0.2.255",
        "port": 9,
    }
    values.update(overrides)
    return WakeTarget(**values)


def test_magic_packet_is_six_ff_plus_mac_repeated_sixteen_times() -> None:
    packet = magic_packet("00:11:22:33:44:55")
    mac = bytes.fromhex("001122334455")

    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6
    assert packet[6:] == mac * 16


def test_common_mac_separators_normalize_to_same_packet() -> None:
    assert magic_packet("00:11:22:33:44:55") == magic_packet("00-11-22-33-44-55")


def test_capability_absent_performs_no_network_action() -> None:
    sender = FakeSender()
    report = BoneThrower(sender).throw(target(wake_on_lan=False))

    assert report.outcome is BoneThrowOutcome.NOT_CAPABLE
    assert sender.calls == []


def test_invalid_mac_is_rejected_without_guessing() -> None:
    sender = FakeSender()
    report = BoneThrower(sender).throw(target(mac_address="00:11:22"))

    assert report.outcome is BoneThrowOutcome.INVALID_TARGET
    assert sender.calls == []


def test_invalid_broadcast_address_is_rejected() -> None:
    sender = FakeSender()
    report = BoneThrower(sender).throw(target(broadcast_address="not-an-ip"))

    assert report.outcome is BoneThrowOutcome.INVALID_TARGET
    assert sender.calls == []


def test_valid_target_sends_exactly_one_packet() -> None:
    sender = FakeSender()
    report = BoneThrower(sender).throw(target())

    assert report.outcome is BoneThrowOutcome.SENT
    assert report.bytes_sent == 102
    assert len(sender.calls or []) == 1
    packet, host, port = sender.calls[0]
    assert packet == magic_packet("00:11:22:33:44:55")
    assert host == "192.0.2.255"
    assert port == 9


def test_socket_send_failure_is_local_error_and_not_retried() -> None:
    sender = FakeSender(fail=OSError("network down"))
    report = BoneThrower(sender).throw(target())

    assert report.outcome is BoneThrowOutcome.LOCAL_ERROR
    assert "OSError" in (report.message or "")
    assert len(sender.calls or []) == 1


def test_short_send_is_local_error() -> None:
    sender = FakeSender(short_by=1)
    report = BoneThrower(sender).throw(target())

    assert report.outcome is BoneThrowOutcome.LOCAL_ERROR
    assert report.bytes_sent == 101


def test_missing_private_wake_hints_are_invalid_not_guessed() -> None:
    sender = FakeSender()
    report = BoneThrower(sender).throw(
        target(mac_address=None, broadcast_address=None)
    )

    assert report.outcome is BoneThrowOutcome.INVALID_TARGET
    assert sender.calls == []
