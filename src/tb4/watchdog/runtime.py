from __future__ import annotations

import json
import platform
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.schemas import canonical_json_text, load_schema_store
from tb4.drive.body_keeper import BodyKeeper
from tb4.drive.delete_keeper import DeleteKeeper
from tb4.drive.device_registration import DeviceProfile, DeviceRegistrar
from tb4.drive.state_walker import StateWalker
from tb4.fetcher.heartbeat import HeartbeatPublisher
from tb4.runtime_support import (
    RuntimeConfigurationError,
    RuntimeContext,
    build_context,
    require_string,
    require_table,
)
from tb4.watchdog.job_reaper import JobReaper
from tb4.watchdog.lan_discovery import LanDiscovery
from tb4.watchdog.openssh_transport import OpenSshBootstrapTransport
from tb4.watchdog.retention import BoneyardKeeper, RetentionPolicy
from tb4.watchdog.scheduler import DogMode, ScheduledTask, WatchdogScheduler
from tb4.watchdog.sniffer import KnownDeviceSniffer, KnownDeviceTarget
from tb4.watchdog.ssh_bootstrap import BootstrapPlatform, BootstrapTarget, DoorScratcher
from tb4.watchdog.stray_hunter import StrayHunter
from tb4.watchdog.system_probe import SystemPingProbe
from tb4.watchdog.wake_manager import WakeManager, WakeTiming
from tb4.watchdog.wol import BoneThrower, UdpBroadcastSender, WakeTarget


@dataclass(frozen=True, slots=True)
class TargetRuntime:
    device_id: str
    probe_target: KnownDeviceTarget
    sniffer: KnownDeviceSniffer
    wake_manager: WakeManager
    job_reaper: JobReaper
    retention: BoneyardKeeper
    fetch_ball_id: str
    wake_bone_id: str


@dataclass(slots=True)
class WatchdogRuntime:
    context: RuntimeContext
    device_id: str
    walker: StateWalker
    heartbeat: HeartbeatPublisher
    scheduler: WatchdogScheduler
    targets: tuple[TargetRuntime, ...]
    dog_mode_id: str
    awake_lease_s: float
    poll_ceiling_s: float
    _last_activity_monotonic_s: float | None = None

    def run(self, stop_event: threading.Event) -> int:
        self._publish_watchdog_identity()
        self._set_mode(DogMode.SNOOZE)
        first_pulse = self.heartbeat.tick(active=False)
        if first_pulse.outcome.value not in {"PUBLISHED", "NOT_DUE"}:
            raise RuntimeError(
                f"initial WATCHDOG heartbeat failed: {first_pulse.outcome.value}"
            )

        while not stop_event.is_set():
            self.scheduler.run_due()
            delay = self.scheduler.next_wakeup_in()
            if delay is None:
                delay = self.poll_ceiling_s
            else:
                delay = min(self.poll_ceiling_s, max(0.05, delay))
            stop_event.wait(delay)
        return 0

    def mark_activity(self) -> None:
        self._last_activity_monotonic_s = time.monotonic()
        self._set_mode(DogMode.AWAKE)

    def maybe_snooze(self) -> None:
        if self.scheduler.mode is not DogMode.AWAKE:
            return
        if self._last_activity_monotonic_s is None:
            return
        if time.monotonic() - self._last_activity_monotonic_s >= self.awake_lease_s:
            self._set_mode(DogMode.SNOOZE)

    def _set_mode(self, mode: DogMode) -> None:
        desired_name = "DOG_AWAKE" if mode is DogMode.AWAKE else "DOG_SNOOZE"
        metadata = self.context.backend.get_metadata(self.dog_mode_id)
        if not metadata.ok or metadata.value is None:
            raise RuntimeError("DOG_MODE metadata is unavailable")
        if metadata.value.name == desired_name:
            self.scheduler.set_mode(mode)
            return

        expected = (
            "SNOOZE"
            if metadata.value.name == "DOG_SNOOZE"
            else "AWAKE"
            if metadata.value.name == "DOG_AWAKE"
            else None
        )
        if expected is None:
            raise RuntimeError(
                f"unexpected WATCHDOG mode object name {metadata.value.name!r}"
            )
        result = self.walker.walk(
            object_id=self.dog_mode_id,
            logical_object=LogicalObject.WATCHDOG_MODE,
            expected_state=expected,
            target_state=mode.value,
            actor=Role.WATCHDOG,
        )
        if not result.success:
            raise RuntimeError(
                f"WATCHDOG mode transition failed: {result.outcome.value}"
            )
        self.scheduler.set_mode(mode)

    def _publish_watchdog_identity(self) -> None:
        tag_id = self.context.park_map.lookup("DOG_HOUSE.DOG_TAG")
        family = platform.system().upper()
        if family not in {"WINDOWS", "LINUX", "MACOS"}:
            family = "OTHER"
        body = {
            "schema_version": 1,
            "protocol_major": 1,
            "device_id": self.device_id,
            "hostname": socket.gethostname(),
            "os_family": family,
            "capabilities": {
                "wake_on_lan": False,
                "ssh_bootstrap": False,
                "fetcher_ephemeral": False,
                "inline_commands": False,
                "script_artifacts": False,
            },
        }
        load_schema_store().validate("dog-tag.schema.json", body)
        text = canonical_json_text(body)

        metadata = self.context.backend.get_metadata(tag_id)
        if not metadata.ok or metadata.value is None:
            raise RuntimeError("WATCHDOG DOG_TAG metadata is unavailable")
        write = self.context.backend.replace_text(
            tag_id,
            text,
            expected_version_token=metadata.value.version_token,
        )
        if not write.ok and write.outcome.value != "AMBIGUOUS":
            raise RuntimeError("WATCHDOG DOG_TAG write failed")
        readback = self.context.backend.read_text(tag_id)
        if not readback.ok or readback.value is None or readback.value.text != text:
            raise RuntimeError("WATCHDOG DOG_TAG write was not remotely confirmed")


def _targets(config: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    multi = config.get("targets")
    if multi is not None:
        if not isinstance(multi, list) or not multi:
            raise RuntimeConfigurationError("[[targets]] must contain at least one target")
        if not all(isinstance(item, Mapping) for item in multi):
            raise RuntimeConfigurationError("every [[targets]] entry must be a table")
        return list(multi)

    single = config.get("target")
    if isinstance(single, Mapping):
        return [single]
    raise RuntimeConfigurationError("WATCHDOG configuration requires [target] or [[targets]]")


def _string_list(table: Mapping[str, Any], key: str) -> tuple[str, ...]:
    raw = table.get(key)
    if not isinstance(raw, list) or not raw or not all(
        isinstance(item, str) and item.strip() for item in raw
    ):
        raise RuntimeConfigurationError(f"{key!r} must be a non-empty string list")
    return tuple(dict.fromkeys(item.strip() for item in raw))


def _bool(table: Mapping[str, Any], key: str) -> bool:
    value = table.get(key)
    if not isinstance(value, bool):
        raise RuntimeConfigurationError(f"{key!r} must be boolean")
    return value


def create_runtime_from_context(context: RuntimeContext) -> WatchdogRuntime:
    config = context.config
    watchdog_cfg = require_table(config, "watchdog")
    service_cfg = require_table(config, "service")
    watchdog_id = require_string(watchdog_cfg, "device_id")
    defaults = context.defaults

    park_map = context.park_map
    registrar = DeviceRegistrar(context.backend)
    target_configs = _targets(config)

    for target in target_configs:
        wol_cfg = require_table(target, "wol")
        ssh_cfg = require_table(target, "ssh_bootstrap")
        profile = DeviceProfile(
            device_id=require_string(target, "device_id"),
            device_key=require_string(target, "device_key"),
            hostname=(
                str(target["hostname"])
                if target.get("hostname") is not None
                else None
            ),
            os_family=require_string(target, "os_family"),
            wake_on_lan=_bool(wol_cfg, "enabled"),
            ssh_bootstrap=_bool(ssh_cfg, "enabled"),
            fetcher_ephemeral=True,
        )
        park_map = registrar.register(park_map, profile).park_map

    context = RuntimeContext(
        config=context.config,
        defaults=context.defaults,
        backend=context.backend,
        park_map=park_map,
        retry_policy=context.retry_policy,
    )

    walker = StateWalker(
        context.backend,
        context.retry_policy,
        time.monotonic,
        time.sleep,
    )
    keeper = BodyKeeper(
        context.backend,
        context.retry_policy,
        time.monotonic,
        time.sleep,
    )

    watchdog_defaults = defaults["watchdog"]
    network_defaults = defaults["network"]
    wake_defaults = defaults["wake"]

    heartbeat = HeartbeatPublisher(
        backend=context.backend,
        dog_pulse_object_id=park_map.lookup("DOG_HOUSE.DOG_PULSE"),
        device_id=watchdog_id,
        instance_id=f"watchdog-{uuid.uuid4().hex}",
        idle_interval_s=float(watchdog_defaults["heartbeat_idle_s"]),
        active_interval_s=float(watchdog_defaults["heartbeat_active_s"]),
        retry_policy=context.retry_policy,
        monotonic_now=time.monotonic,
        epoch_now=lambda: int(time.time()),
        sleeper=time.sleep,
    )

    scheduler = WatchdogScheduler(time.monotonic)
    local_probe = SystemPingProbe()
    door = DoorScratcher(OpenSshBootstrapTransport())
    bone = BoneThrower(UdpBroadcastSender())

    network_cfg = config.get("network", {})
    if not isinstance(network_cfg, Mapping):
        raise RuntimeConfigurationError("[network] must be a table")
    discovery_cidrs_raw = network_cfg.get("discovery_cidrs", [])
    if not isinstance(discovery_cidrs_raw, list) or not all(
        isinstance(item, str) and item.strip() for item in discovery_cidrs_raw
    ):
        raise RuntimeConfigurationError("network.discovery_cidrs must be a string list")
    discovery = LanDiscovery(
        cidrs=tuple(item.strip() for item in discovery_cidrs_raw),
        max_hosts=int(network_cfg.get("discovery_max_hosts", 1024)),
        workers=int(network_cfg.get("discovery_workers", 16)),
    )
    stray_hunter = StrayHunter(
        backend=context.backend,
        discovery=discovery,
        stray_yard_folder_id=park_map.lookup("STRAY_YARD"),
        retry_policy=context.retry_policy,
        epoch_now=lambda: int(time.time()),
        monotonic_now=time.monotonic,
        sleeper=time.sleep,
    )

    runtime_targets: list[TargetRuntime] = []
    runtime_holder: dict[str, WatchdogRuntime] = {}

    for target in target_configs:
        device_id = require_string(target, "device_id")
        wol_cfg = require_table(target, "wol")
        ssh_cfg = require_table(target, "ssh_bootstrap")
        addresses = _string_list(target, "address_hints")
        mac = wol_cfg.get("mac")
        if mac is not None and not isinstance(mac, str):
            raise RuntimeConfigurationError("target.wol.mac must be a string")
        sniff_target = KnownDeviceTarget(
            device_id,
            park_map.lookup_device(device_id, "DOG_SNIFF"),
            addresses,
            mac,
        )
        sniffer = KnownDeviceSniffer(
            backend=context.backend,
            local_probe=local_probe,
            retry_policy=context.retry_policy,
            freshness_s=float(network_defaults["known_device_publish_s"]),
            monotonic_now=time.monotonic,
            epoch_now=lambda: int(time.time()),
            sleeper=time.sleep,
        )

        wol_enabled = _bool(wol_cfg, "enabled")
        broadcast = wol_cfg.get("broadcast_address")
        if broadcast is not None and not isinstance(broadcast, str):
            raise RuntimeConfigurationError("target.wol.broadcast_address must be a string")
        wake_target = WakeTarget(
            wol_enabled,
            mac if wol_enabled else None,
            broadcast if wol_enabled else None,
            int(wol_cfg.get("port", 9)),
        )

        ssh_enabled = _bool(ssh_cfg, "enabled")
        platform_name = str(ssh_cfg.get("platform", "LINUX_SYSTEMD"))
        try:
            bootstrap_platform = BootstrapPlatform(platform_name)
        except ValueError as exc:
            raise RuntimeConfigurationError(
                f"invalid SSH bootstrap platform {platform_name!r}"
            ) from exc
        host_alias = ssh_cfg.get("host_alias")
        if host_alias is not None and not isinstance(host_alias, str):
            raise RuntimeConfigurationError("target.ssh_bootstrap.host_alias must be a string")
        bootstrap_target = BootstrapTarget(
            ssh_enabled,
            host_alias if ssh_enabled else None,
            "OPENSSH_CONFIG" if ssh_enabled else None,
            bootstrap_platform,
        )

        manager = WakeManager(
            backend=context.backend,
            state_walker=walker,
            body_keeper=keeper,
            bone_thrower=bone,
            door_scratcher=door,
            local_probe=local_probe,
            wake_bone_object_id=park_map.lookup_device(device_id, "KENNEL.WAKE_BONE"),
            dog_pulse_object_id=park_map.lookup_device(device_id, "DOG_PULSE"),
            target_device_id=device_id,
            probe_target=sniff_target,
            wake_target=wake_target,
            bootstrap_target=bootstrap_target,
            timing=WakeTiming(
                float(wake_defaults["wol_initial_wait_s"]),
                float(wake_defaults["probe_interval_s"]),
                float(wake_defaults["wake_deadline_s"]),
                int(watchdog_defaults["stale_active_s"]),
                int(watchdog_defaults["clock_skew_tolerance_s"]),
            ),
            monotonic_now=time.monotonic,
            epoch_now=lambda: int(time.time()),
            sleeper=time.sleep,
        )

        reaper = JobReaper(
            backend=context.backend,
            state_walker=walker,
            body_keeper=keeper,
            fetch_ball_object_id=park_map.lookup_device(device_id, "PLAYGROUND.FETCH_BALL"),
            dog_pulse_object_id=park_map.lookup_device(device_id, "DOG_PULSE"),
            target_device_id=device_id,
            stale_after_s=int(watchdog_defaults["stale_active_s"]),
            gone_grace_s=int(defaults["fetcher"]["gone_grace_s"]),
            clock_skew_tolerance_s=int(watchdog_defaults["clock_skew_tolerance_s"]),
            epoch_now=lambda: int(time.time()),
        )

        fetch_ball_id = park_map.lookup_device(device_id, "PLAYGROUND.FETCH_BALL")
        retention_defaults = defaults["retention"]
        retention = BoneyardKeeper(
            backend=context.backend,
            delete_keeper=DeleteKeeper(
                context.backend,
                context.retry_policy,
                time.monotonic,
                time.sleep,
            ),
            boneyard_folder_id=park_map.lookup_device(device_id, "BONEYARD"),
            toy_box_folder_id=park_map.lookup_device(device_id, "TOY_BOX"),
            policy=RetentionPolicy(
                boneyard_retention_s=int(retention_defaults["boneyard_days"]) * 86400,
                toy_box_retention_s=int(retention_defaults["toy_box_days"]) * 86400,
            ),
            epoch_now=lambda: int(time.time()),
            clock_safe=lambda: 1_577_836_800 <= int(time.time()) <= 4_102_444_800,
        )

        entry = TargetRuntime(
            device_id=device_id,
            probe_target=sniff_target,
            sniffer=sniffer,
            wake_manager=manager,
            job_reaper=reaper,
            retention=retention,
            fetch_ball_id=fetch_ball_id,
            wake_bone_id=park_map.lookup_device(device_id, "KENNEL.WAKE_BONE"),
        )
        runtime_targets.append(entry)

        scheduler.register(
            ScheduledTask(
                name=f"sniff:{device_id}",
                callback=lambda _reason, item=entry: item.sniffer.probe_once(item.probe_target),
                snooze_interval_s=float(network_defaults["known_device_probe_s"]),
                awake_interval_s=float(network_defaults["known_device_probe_s"]),
                phase_key=f"sniff:{device_id}",
            )
        )

        def wake_check(_reason, item=entry):
            metadata = context.backend.get_metadata(item.wake_bone_id)
            if not metadata.ok or metadata.value is None:
                return
            if metadata.value.name == "WAKE_BONE_TOSS":
                runtime_holder["runtime"].mark_activity()
                item.wake_manager.process_toss()

        scheduler.register(
            ScheduledTask(
                name=f"wake:{device_id}",
                callback=wake_check,
                snooze_interval_s=float(network_defaults["known_device_probe_s"]),
                awake_interval_s=max(1.0, float(wake_defaults["probe_interval_s"])),
                phase_key=f"wake:{device_id}",
            )
        )

        scheduler.register(
            ScheduledTask(
                name=f"reap:{device_id}",
                callback=lambda _reason, item=entry: item.job_reaper.check_once(),
                snooze_interval_s=float(network_defaults["known_device_probe_s"]),
                awake_interval_s=max(1.0, float(watchdog_defaults["heartbeat_active_s"])),
                phase_key=f"reap:{device_id}",
            )
        )

        def retention_sweep(_reason, item=entry):
            protected: list[str] = []
            remote = context.backend.read_text(item.fetch_ball_id)
            if remote.ok and remote.value is not None:
                try:
                    active = json.loads(remote.value.text)
                    refs = active.get("artifact_refs", [])
                    if isinstance(refs, list):
                        for ref in refs:
                            if isinstance(ref, Mapping):
                                artifact_id = ref.get("artifact_id")
                                if isinstance(artifact_id, str) and artifact_id:
                                    protected.append(artifact_id)
                except (json.JSONDecodeError, TypeError):
                    # Malformed live control state must not cause retention to
                    # guess what is safe to delete; skip this sweep entirely.
                    return None
            else:
                return None
            return item.retention.sweep(protected_artifact_ids=protected)

        scheduler.register(
            ScheduledTask(
                name=f"bury:{device_id}",
                callback=retention_sweep,
                snooze_interval_s=float(retention_defaults["sweep_interval_s"]),
                awake_interval_s=float(retention_defaults["sweep_interval_s"]),
                phase_key=f"bury:{device_id}",
            )
        )

    scheduler.register(
        ScheduledTask(
            name="stray-hunt",
            callback=lambda _reason: stray_hunter.scan_once(),
            snooze_interval_s=float(network_defaults["stray_scan_s"]),
            awake_interval_s=float(network_defaults["stray_scan_s"]),
            phase_key="stray-hunt",
        )
    )

    scheduler.register(
        ScheduledTask(
            name="dog-pulse",
            callback=lambda _reason: heartbeat.tick(
                active=scheduler.mode is DogMode.AWAKE
            ),
            snooze_interval_s=float(watchdog_defaults["heartbeat_idle_s"]),
            awake_interval_s=float(watchdog_defaults["heartbeat_active_s"]),
            phase_key="dog-pulse",
        )
    )
    scheduler.register(
        ScheduledTask(
            name="dog-snooze-check",
            callback=lambda _reason: runtime_holder["runtime"].maybe_snooze(),
            snooze_interval_s=30.0,
            awake_interval_s=5.0,
            phase_key="dog-snooze-check",
        )
    )

    runtime = WatchdogRuntime(
        context=context,
        device_id=watchdog_id,
        walker=walker,
        heartbeat=heartbeat,
        scheduler=scheduler,
        targets=tuple(runtime_targets),
        dog_mode_id=park_map.lookup("DOG_HOUSE.WATCHDOG_MODE"),
        awake_lease_s=float(watchdog_defaults["awake_lease_s"]),
        poll_ceiling_s=float(service_cfg.get("poll_interval_s", 1.0)),
    )
    if runtime.poll_ceiling_s <= 0:
        raise RuntimeConfigurationError("service.poll_interval_s must be positive")
    runtime_holder["runtime"] = runtime
    return runtime


def create_runtime(config_path: Path):
    return create_runtime_from_context(build_context(config_path))
