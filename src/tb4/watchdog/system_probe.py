from __future__ import annotations

import math
import platform
import shutil
import subprocess
from dataclasses import dataclass

from tb4.watchdog.sniffer import (
    KnownDeviceTarget,
    ProbeKind,
    ProbeObservation,
    Reachability,
)


@dataclass(slots=True)
class SystemPingProbe:
    """Bounded no-shell ICMP probe for known private deployment targets."""

    timeout_s: float = 1.5

    def __post_init__(self) -> None:
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive")

    def probe(self, target: KnownDeviceTarget) -> ProbeObservation:
        addresses = tuple(dict.fromkeys(item.strip() for item in target.address_hints if item.strip()))
        if not addresses:
            return ProbeObservation(
                Reachability.UNKNOWN,
                ProbeKind.NONE,
                (),
                target.mac_address,
            )

        ping = shutil.which("ping")
        if ping is None:
            return ProbeObservation(
                Reachability.UNKNOWN,
                ProbeKind.NONE,
                addresses,
                target.mac_address,
            )

        for address in addresses:
            args = self._argv(ping, address)
            try:
                result = subprocess.run(
                    args,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=self.timeout_s + 1.0,
                    check=False,
                    shell=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode == 0:
                return ProbeObservation(
                    Reachability.ONLINE,
                    ProbeKind.ICMP,
                    addresses,
                    target.mac_address,
                )

        return ProbeObservation(
            Reachability.OFFLINE,
            ProbeKind.ICMP,
            addresses,
            target.mac_address,
        )

    def _argv(self, ping: str, address: str) -> list[str]:
        if platform.system().lower().startswith("win"):
            return [
                ping,
                "-n",
                "1",
                "-w",
                str(max(1, int(self.timeout_s * 1000))),
                address,
            ]
        return [
            ping,
            "-c",
            "1",
            "-W",
            str(max(1, int(math.ceil(self.timeout_s)))),
            address,
        ]
