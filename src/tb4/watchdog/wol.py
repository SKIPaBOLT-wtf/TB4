from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


WOL_PORT_DEFAULT = 9


class BoneThrowOutcome(StrEnum):
    SENT = "SENT"
    NOT_CAPABLE = "NOT_CAPABLE"
    INVALID_TARGET = "INVALID_TARGET"
    LOCAL_ERROR = "LOCAL_ERROR"


@dataclass(frozen=True, slots=True)
class WakeTarget:
    """Private/runtime wake hints for one target.

    Only `wake_on_lan` is expected to originate from the public DOG_TAG
    capability declaration. MAC/broadcast hints belong to deployment-local
    configuration and must not be inferred or guessed by this helper.
    """

    wake_on_lan: bool
    mac_address: str | None
    broadcast_address: str | None
    port: int = WOL_PORT_DEFAULT


@dataclass(frozen=True, slots=True)
class BoneThrowReport:
    outcome: BoneThrowOutcome
    bytes_sent: int = 0
    message: str | None = None


@runtime_checkable
class DatagramSender(Protocol):
    def send(self, payload: bytes, host: str, port: int) -> int:
        ...


class UdpBroadcastSender:
    """One-shot UDP broadcast sender used by BONE_THROWER."""

    def send(self, payload: bytes, host: str, port: int) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            return sock.sendto(payload, (host, port))


def parse_mac(mac_address: str) -> bytes:
    compact = (
        mac_address.strip()
        .lower()
        .replace(":", "")
        .replace("-", "")
        .replace(".", "")
    )
    if len(compact) != 12:
        raise ValueError("MAC address must contain exactly 6 bytes")
    try:
        raw = bytes.fromhex(compact)
    except ValueError as exc:
        raise ValueError("MAC address contains non-hexadecimal characters") from exc
    if len(raw) != 6:
        raise ValueError("MAC address must contain exactly 6 bytes")
    return raw


def magic_packet(mac_address: str) -> bytes:
    mac = parse_mac(mac_address)
    return b"\xff" * 6 + mac * 16


@dataclass(slots=True)
class BoneThrower:
    sender: DatagramSender

    def throw(self, target: WakeTarget) -> BoneThrowReport:
        if not target.wake_on_lan:
            return BoneThrowReport(
                BoneThrowOutcome.NOT_CAPABLE,
                message="target does not advertise wake_on_lan capability",
            )

        if target.mac_address is None or target.broadcast_address is None:
            return BoneThrowReport(
                BoneThrowOutcome.INVALID_TARGET,
                message="MAC and broadcast address are required for Wake-on-LAN",
            )

        try:
            packet = magic_packet(target.mac_address)
            host = str(ipaddress.IPv4Address(target.broadcast_address))
        except ValueError as exc:
            return BoneThrowReport(
                BoneThrowOutcome.INVALID_TARGET,
                message=str(exc),
            )

        if not 1 <= int(target.port) <= 65535:
            return BoneThrowReport(
                BoneThrowOutcome.INVALID_TARGET,
                message="UDP port must be between 1 and 65535",
            )

        try:
            sent = int(self.sender.send(packet, host, int(target.port)))
        except Exception as exc:
            return BoneThrowReport(
                BoneThrowOutcome.LOCAL_ERROR,
                message=f"{type(exc).__name__}: {exc}",
            )

        if sent != len(packet):
            return BoneThrowReport(
                BoneThrowOutcome.LOCAL_ERROR,
                bytes_sent=sent,
                message=f"short UDP send: {sent}/{len(packet)} bytes",
            )

        return BoneThrowReport(BoneThrowOutcome.SENT, bytes_sent=sent)
