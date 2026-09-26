from __future__ import annotations

from tb4.watchdog.lan_discovery import LanDiscovery


def test_neighbor_parser_groups_addresses_by_stable_mac() -> None:
    observations: dict[str, set[str]] = {}
    LanDiscovery._parse_neighbor_text(
        """
192.0.2.10 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE
? (192.0.2.11) at 00-11-22-33-44-55 on eth0
198.51.100.7 dev eth0 FAILED
""",
        observations,
    )
    assert observations == {
        "00:11:22:33:44:55": {"192.0.2.10", "192.0.2.11"}
    }


def test_explicit_discovery_scope_is_bounded() -> None:
    try:
        LanDiscovery(cidrs=("192.0.2.0/24",), max_hosts=10)
    except ValueError as exc:
        assert "max_hosts" in str(exc)
    else:
        raise AssertionError("oversized discovery scope must fail closed")


def test_scan_without_cidrs_performs_no_active_ping(monkeypatch) -> None:
    called = []

    discovery = LanDiscovery()
    monkeypatch.setattr(discovery, "_ping", lambda address: called.append(address))
    monkeypatch.setattr(discovery, "_neighbors", lambda: ())

    assert discovery.scan() == ()
    assert called == []


def test_explicit_cidr_uses_host_addresses_only(monkeypatch) -> None:
    called = []
    discovery = LanDiscovery(cidrs=("192.0.2.0/30",), max_hosts=10, workers=1)
    monkeypatch.setattr(discovery, "_ping", lambda address: called.append(address))
    monkeypatch.setattr(discovery, "_neighbors", lambda: ())

    discovery.scan()

    assert called == ["192.0.2.1", "192.0.2.2"]


def test_neighbor_commands_never_use_shell(monkeypatch) -> None:
    observed = []

    class Result:
        returncode = 0
        stdout = "192.0.2.10 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE\n"

    def fake_which(name):
        return f"/usr/bin/{name}" if name in {"ip", "arp"} else None

    def fake_run(argv, **kwargs):
        observed.append((argv, kwargs))
        return Result()

    monkeypatch.setattr("tb4.watchdog.lan_discovery.shutil.which", fake_which)
    monkeypatch.setattr("tb4.watchdog.lan_discovery.subprocess.run", fake_run)

    devices = LanDiscovery().scan()

    assert len(devices) == 1
    assert devices[0].mac_address == "00:11:22:33:44:55"
    assert all(kwargs["shell"] is False for _, kwargs in observed)
