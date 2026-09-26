from __future__ import annotations

import ipaddress
import platform
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from tb4.watchdog.stray_hunter import DiscoveredDevice


_IPV4_RE = re.compile(r"(?<![0-9.])(?:\d{1,3}\.){3}\d{1,3}(?![0-9.])")
_MAC_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])")


@dataclass(slots=True)
class LanDiscovery:
    """Low-frequency bounded LAN discovery.

    With no CIDRs this reads the operating-system neighbor table only. When
    explicit private CIDRs are configured, a bounded ICMP sweep is performed
    first solely to refresh neighbor observations. No ports are scanned.
    """

    cidrs: tuple[str, ...] = ()
    ping_timeout_s: float = 0.5
    max_hosts: int = 1024
    workers: int = 16

    def __post_init__(self) -> None:
        if self.ping_timeout_s <= 0:
            raise ValueError("ping_timeout_s must be positive")
        if self.max_hosts <= 0:
            raise ValueError("max_hosts must be positive")
        if not 1 <= self.workers <= 64:
            raise ValueError("workers must be between 1 and 64")
        self._hosts()  # validate CIDRs and global bound eagerly

    def scan(self) -> tuple[DiscoveredDevice, ...]:
        hosts = self._hosts()
        if hosts:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                tuple(pool.map(self._ping, hosts))
        return self._neighbors()

    def _hosts(self) -> tuple[str, ...]:
        found: list[str] = []
        seen: set[str] = set()
        for raw in self.cidrs:
            try:
                network = ipaddress.ip_network(raw, strict=False)
            except ValueError as exc:
                raise ValueError(f"invalid discovery CIDR {raw!r}") from exc
            if not isinstance(network, ipaddress.IPv4Network):
                raise ValueError("TB4 v1 LAN discovery supports IPv4 CIDRs only")
            for address in network.hosts():
                text = str(address)
                if text in seen:
                    continue
                seen.add(text)
                found.append(text)
                if len(found) > self.max_hosts:
                    raise ValueError(
                        f"configured discovery scope exceeds max_hosts={self.max_hosts}"
                    )
        return tuple(found)

    def _ping(self, address: str) -> None:
        executable = shutil.which("ping")
        if executable is None:
            return
        system = platform.system().lower()
        if system.startswith("win"):
            argv = [
                executable,
                "-n",
                "1",
                "-w",
                str(max(1, int(self.ping_timeout_s * 1000))),
                address,
            ]
        else:
            # Integer timeout keeps compatibility with common iputils ping.
            argv = [
                executable,
                "-c",
                "1",
                "-W",
                str(max(1, int(self.ping_timeout_s + 0.999))),
                address,
            ]
        try:
            subprocess.run(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.ping_timeout_s + 1.5,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return

    def _neighbors(self) -> tuple[DiscoveredDevice, ...]:
        commands: list[list[str]] = []
        ip_cmd = shutil.which("ip")
        arp_cmd = shutil.which("arp")
        if ip_cmd is not None:
            commands.append([ip_cmd, "neigh", "show"])
        if arp_cmd is not None:
            commands.append([arp_cmd, "-a"])

        observations: dict[str, set[str]] = {}
        for argv in commands:
            try:
                completed = subprocess.run(
                    argv,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                    check=False,
                    shell=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if completed.returncode != 0:
                continue
            self._parse_neighbor_text(completed.stdout, observations)

        devices = [
            DiscoveredDevice(
                addresses=tuple(sorted(addresses)),
                mac_address=mac,
                discovery_kind="LAN_NEIGHBOR",
            )
            for mac, addresses in sorted(observations.items())
        ]
        return tuple(devices)

    @staticmethod
    def _parse_neighbor_text(
        text: str,
        observations: dict[str, set[str]],
    ) -> None:
        for line in text.splitlines():
            mac_match = _MAC_RE.search(line)
            if mac_match is None:
                continue
            mac = mac_match.group(0).replace("-", ":").upper()
            addresses: set[str] = set()
            for match in _IPV4_RE.finditer(line):
                raw = match.group(0)
                try:
                    address = ipaddress.IPv4Address(raw)
                except ipaddress.AddressValueError:
                    continue
                if address.is_unspecified or address.is_multicast:
                    continue
                addresses.add(str(address))
            if addresses:
                observations.setdefault(mac, set()).update(addresses)
