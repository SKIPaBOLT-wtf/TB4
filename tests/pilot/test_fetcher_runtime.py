from __future__ import annotations

import importlib
import threading
from pathlib import Path

from tb4.drive.bootstrap import bootstrap_tree
from tb4.drive.device_registration import DeviceProfile, DeviceRegistrar
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.fetcher.runtime import create_runtime_from_context
from tb4.runtime_support import build_context


def _registered_backend() -> InMemoryDriveBackend:
    backend = InMemoryDriveBackend()
    base = bootstrap_tree(backend, root_id=backend.root_id).park_map
    DeviceRegistrar(backend).register(
        base,
        DeviceProfile(
            device_id="device-001",
            device_key="target-a",
            hostname="example-host",
            os_family="LINUX",
            wake_on_lan=False,
            ssh_bootstrap=False,
        ),
    )
    return backend


def _config(path: Path, backend: InMemoryDriveBackend, work: Path) -> Path:
    path.write_text(
        f"""
[identity]
device_id = "device-001"

[drive]
root_id = "{backend.root_id}"
client_secrets_path = "not-used-by-in-memory-test"
token_path = "not-used-by-in-memory-test"

[service]
ephemeral = true
idle_exit_s = 600
poll_interval_s = 0.01

[execution]
artifact_work_dir = "{work.as_posix()}"
""",
        encoding="utf-8",
    )
    return path


def test_stable_cli_fetcher_runtime_factory_is_importable() -> None:
    module = importlib.import_module("tb4.fetcher.runtime")
    assert callable(module.create_runtime)


def test_fetcher_runtime_composes_from_registered_exact_ids(tmp_path: Path) -> None:
    backend = _registered_backend()
    context = build_context(
        _config(tmp_path / "fetcher.toml", backend, tmp_path / "work"),
        backend=backend,
    )

    runtime = create_runtime_from_context(context)

    assert runtime.device_id == "device-001"
    assert (
        runtime.fetch_ball_id
        == context.park_map.lookup_device("device-001", "PLAYGROUND.FETCH_BALL")
    )
    assert (
        runtime.stop_ball_id
        == context.park_map.lookup_device("device-001", "PLAYGROUND.STOP_BALL")
    )


def test_fetcher_runtime_starts_publishes_pulse_and_stops_cleanly(tmp_path: Path) -> None:
    backend = _registered_backend()
    context = build_context(
        _config(tmp_path / "fetcher.toml", backend, tmp_path / "work"),
        backend=backend,
    )
    runtime = create_runtime_from_context(context)
    stop = threading.Event()
    stop.set()

    assert runtime.run(stop) == 0

    pulse = backend.read_text(context.park_map.lookup_device("device-001", "DOG_PULSE"))
    assert pulse.ok and pulse.value is not None
    assert '"device_id":"device-001"' in pulse.value.text
