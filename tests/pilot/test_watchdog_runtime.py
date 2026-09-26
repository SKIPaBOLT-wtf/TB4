from __future__ import annotations

import importlib
import json
import threading
from pathlib import Path

from tb4.drive.bootstrap import bootstrap_tree
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.runtime_support import build_context
from tb4.watchdog.runtime import create_runtime_from_context


def _config(path: Path, backend: InMemoryDriveBackend, *, multi: bool = False) -> Path:
    target_blocks = """
[[targets]]
device_id = "device-001"
device_key = "target-a"
hostname = "example-a"
os_family = "LINUX"
address_hints = ["192.0.2.10"]

[targets.wol]
enabled = false

[targets.ssh_bootstrap]
enabled = false
platform = "LINUX_SYSTEMD"
"""
    if multi:
        target_blocks += """
[[targets]]
device_id = "device-002"
device_key = "target-b"
hostname = "example-b"
os_family = "WINDOWS"
address_hints = ["192.0.2.20"]

[targets.wol]
enabled = false

[targets.ssh_bootstrap]
enabled = false
platform = "WINDOWS_SERVICE"
"""
    path.write_text(
        f"""
[watchdog]
device_id = "watchdog-host"

[drive]
root_id = "{backend.root_id}"
client_secrets_path = "not-used-by-in-memory-test"
token_path = "not-used-by-in-memory-test"

[service]
poll_interval_s = 0.01

{target_blocks}
""",
        encoding="utf-8",
    )
    return path


def _backend() -> InMemoryDriveBackend:
    backend = InMemoryDriveBackend()
    bootstrap_tree(backend, root_id=backend.root_id)
    return backend


def test_stable_cli_watchdog_runtime_factory_is_importable() -> None:
    module = importlib.import_module("tb4.watchdog.runtime")
    assert callable(module.create_runtime)


def test_watchdog_runtime_registers_target_before_normal_operation(tmp_path: Path) -> None:
    backend = _backend()
    context = build_context(_config(tmp_path / "watchdog.toml", backend), backend=backend)

    runtime = create_runtime_from_context(context)

    assert len(runtime.targets) == 1
    assert runtime.targets[0].device_id == "device-001"
    assert "device-001" in runtime.context.park_map.devices
    assert runtime.context.park_map.lookup_device("device-001", "PLAYGROUND.FETCH_BALL")


def test_watchdog_runtime_supports_independent_multiple_targets(tmp_path: Path) -> None:
    backend = _backend()
    context = build_context(
        _config(tmp_path / "watchdog.toml", backend, multi=True),
        backend=backend,
    )

    runtime = create_runtime_from_context(context)

    assert [target.device_id for target in runtime.targets] == [
        "device-001",
        "device-002",
    ]
    assert runtime.context.park_map.lookup_device("device-001", "PLAYGROUND.FETCH_BALL") != runtime.context.park_map.lookup_device(
        "device-002", "PLAYGROUND.FETCH_BALL"
    )


def test_watchdog_start_publishes_identity_and_pulse_without_runtime_scan(tmp_path: Path) -> None:
    backend = _backend()
    context = build_context(_config(tmp_path / "watchdog.toml", backend), backend=backend)
    runtime = create_runtime_from_context(context)

    backend.reset_operation_counts()
    stop = threading.Event()
    stop.set()
    assert runtime.run(stop) == 0

    tag = backend.read_text(runtime.context.park_map.lookup("DOG_HOUSE.DOG_TAG"))
    pulse = backend.read_text(runtime.context.park_map.lookup("DOG_HOUSE.DOG_PULSE"))
    assert tag.ok and tag.value is not None
    assert pulse.ok and pulse.value is not None
    assert json.loads(tag.value.text)["device_id"] == "watchdog-host"
    assert json.loads(pulse.value.text)["device_id"] == "watchdog-host"

    # Target registration may enumerate once, but the started normal runtime
    # uses exact PARK_MAP object IDs.
    assert backend.operation_counts.get("list_children", 0) == 0
