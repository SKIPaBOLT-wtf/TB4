"""Bounded discovery using protected setup and the existing fixed authority.

Trusted composition supplies commissioned storage, capabilities, clock, current
grant and a fresh enrollment view. No default live activation or enrollment.
"""
from __future__ import annotations

import secrets
import time

from .commissioning_checks import CommissionedStorage
from .commissioning_state import Setup, storage_spec
from .discovery_catalogue import Catalogue, Scope, TrustView, new_image, require
from .discovery_native import collect_fixed, collect_neighbors
from .discovery_state import (catalogue_record, parse_scope, related_slots,
                              scope_record, validated_package)
from .drive.authority_transaction import OwnerGuard, RecordMutation, reconcile
from .drive.commissioning import frozen_plan, restored_plan
from .drive.leadership import ClockSample, Grant, Leadership
from .watchdog.leadership_runtime import Action, Capabilities


class Discovery:
    def __init__(self, setup, *, storage_port, leadership, grant, clock, capabilities,
                 trust=lambda: TrustView()):
        require(type(setup) is Setup and isinstance(leadership, Leadership)
                and type(grant) is Grant and setup.installation_id == leadership.actor == grant.owner
                and all(callable(f) for f in (clock, capabilities, trust)), "DISCOVERY_CONTEXT")
        self.setup, self.port, self.leader, self.grant = setup, storage_port, leadership, grant
        self.clock, self.capabilities, self.trust = clock, capabilities, trust

    def _local(self, *, allow_cancelled=False):
        self.setup._fresh()
        choices = self.setup.private_choices()
        require(choices["role"] == "watchdog" and choices["storage"] is not None
                and choices["network_scope"] is not None, "DISCOVERY_NOT_CONFIGURED")
        require(allow_cancelled or self.setup._payload["state"] != "CANCELLED", "DISCOVERY_CANCELLED")
        spec, handle = storage_spec(choices["storage"])
        require(self.leader.backend.binding == self.port.authority(handle).binding,
                "DISCOVERY_AUTHORITY_BINDING")
        return choices, spec, handle

    def _package(self, *, allow_cancelled=False):
        choices, spec, handle = self._local(allow_cancelled=allow_cancelled)
        value = self.setup._payload.get("discovery")
        require(value is not None, "DISCOVERY_NOT_CONFIGURED")
        return validated_package(value, installation=self.setup.installation_id, spec=spec,
                                 authority=handle, networks=choices["network_scope"])

    def _save(self, value):
        self.setup._fresh()
        self.setup._save({**self.setup._payload, "discovery": value,
                          "state": self.setup._payload["state"] if self.setup._payload["state"] == "CANCELLED"
                          else "INCOMPLETE", "reason": "CANCELLED" if self.setup._payload["state"] == "CANCELLED"
                          else "REVALIDATION_REQUIRED"})

    def _current(self, action):
        self._local()
        caps = self.capabilities()
        require(type(caps) is Capabilities and caps.installation_id == self.setup.installation_id
                and caps.observe is True and caps.coordinate is True and type(caps.actions) is frozenset
                and action in caps.actions, "DISCOVERY_NOT_AUTHORIZED")
        sample = self.clock()
        require(type(sample) is ClockSample and sample.wall_trusted and sample.monotonic_trusted,
                "DISCOVERY_CLOCK")
        require(self.leader.current_before_dispatch(self.grant, sample), "DISCOVERY_SUPERSEDED")
        return sample.utc

    def _snapshot(self):
        choices, spec, _ = self._local()
        # Verify actual fixed root/allocations, then the exact backend used for CAS.
        CommissionedStorage(self.port).verify(choices["storage"])
        snapshot = self.leader.backend.read()
        document = snapshot.document()
        from dataclasses import asdict
        require(document["domain_id"] == spec.domain_id and document["capacity"] == asdict(spec.capacity)
                and document["records"]["global.commissioning"] == dict(
                    generation=0, operation_id=spec.setup_id, retention="RETAINED",
                    body=spec.marker("STORAGE_READY")), "DISCOVERY_AUTHORITY_BINDING")
        return snapshot

    def configure(self, scope, *, owner_authorized=False):
        require(owner_authorized is True and type(scope) is Scope, "DISCOVERY_NOT_AUTHORIZED")
        _, spec, _ = self._local()
        previous = self.setup._payload.get("discovery")
        if previous is not None:
            require(previous["scope"] == scope_record(scope), "DISCOVERY_RECONFIGURATION_REQUIRED")
            return self.status()
        self._snapshot()
        self._save(dict(schema_version=1, scope=scope_record(scope), pending=None,
                        image=new_image(self.setup.installation_id, spec.domain_id,
                                        capacity=spec.capacity.devices,
                                        quarantine_capacity=spec.capacity.quarantine)))
        return self.status()

    def _adopt(self, catalogue, document):
        image = catalogue.private_image()
        for index, entry in enumerate(image["entries"]):
            row = document["records"][f"target.{index:03d}.catalogue"]
            body = catalogue_record(row).get("discovery")
            if body is None:
                continue
            if entry is None:
                catalogue.seed(index, body["device_id"], body["alias"])
            else:
                require(all(entry[k] == body[k] for k in ("device_id", "alias")),
                        "DISCOVERY_IDENTITY_CONFLICT")

    def observe(self, observations):
        package = self._package()
        require(package["pending"] is None, "DISCOVERY_INSPECT_REQUIRED")
        now = self._current(Action.SCAN)
        snapshot = self._snapshot()
        catalogue = Catalogue(package["image"])
        self._adopt(catalogue, snapshot.document())
        trust = self.trust()
        require(type(trust) is TrustView, "DISCOVERY_TRUST")
        outcomes = catalogue.observe(observations, parse_scope(package["scope"]), now=now, trust=trust)
        image = catalogue.private_image()
        if image != package["image"]:
            self._save({**package, "image": image})  # IDs are durable before any publication.
        if self.setup._payload.get("network_table") is not None:
            from .network_table_store import LocalNetworkTable
            from .network_table import NetworkTableError
            try:
                LocalNetworkTable(self.setup).sync_observations(
                    image, current_owner=lambda: bool(self._current(Action.SCAN) >= 0))
            except NetworkTableError:
                # Discovery is still evidence. The table reports its own pending/
                # unavailable status; never erase observations or retry its write.
                pass
        return outcomes

    def collect(self, port, *, targets=None, monotonic=time.monotonic):
        """Fixed trusted ports; owner is refreshed before each helper/cache call."""
        package = self._package()
        require(package["pending"] is None, "DISCOVERY_INSPECT_REQUIRED")
        self._current(Action.SCAN)
        scope = parse_scope(package["scope"])
        workflow = self

        class Guarded:
            def inspect(self, interface, *, timeout):
                workflow._current(Action.SCAN)
                return port.inspect(interface, timeout=timeout)

            def read(self, interface, *, timeout):
                workflow._current(Action.SCAN)
                return port.read(interface, timeout=timeout)

            def observe(self, request, *, timeout):
                workflow._current(Action.SCAN)
                return port.observe(request, timeout=timeout)

        if targets is None:
            result = collect_neighbors(scope, Guarded(), clock=lambda: self._current(Action.SCAN),
                                       monotonic=monotonic)
        else:
            result = collect_fixed(scope, targets, Guarded(), now=self._current(Action.SCAN),
                                   monotonic=monotonic)
        self.observe(result.observations)
        return result.summary()

    def publish(self):
        package = self._package()
        require(package["pending"] is None, "DISCOVERY_INSPECT_REQUIRED")
        now = self._current(Action.REGISTER)
        snapshot = self._snapshot()
        records = snapshot.document()["records"]
        catalogue = Catalogue(package["image"])
        self._adopt(catalogue, snapshot.document())
        if catalogue.private_image() != package["image"]:
            package = {**package, "image": catalogue.private_image()}
            self._save(package)
        trust = self.trust()
        require(type(trust) is TrustView, "DISCOVERY_TRUST")
        changes, protected, operation = {}, {"global.commissioning"}, secrets.token_hex(32)

        def change(key, body):
            row = records[key]
            require(row["generation"] < 2**63-1, "DISCOVERY_GENERATION_EXHAUSTED")
            changes[key] = dict(generation=row["generation"]+1, operation_id=operation,
                                retention="RETAINED", body=body)

        for row in catalogue.shared(now=now, trust=trust):
            index = row["slot"]
            if not package["image"]["entries"][index]["endpoints"]:
                continue  # Adoption alone cannot downgrade another observer's evidence.
            key = f"target.{index:03d}.catalogue"
            old = records[key]
            existing = catalogue_record(old)
            body = {**existing, "discovery": {"schema_version": 1, "kind": "DISCOVERY",
                                            **{k:v for k,v in row.items() if k != "slot"}}}
            previous_network = existing.get("discovery", {}).get("network")
            network = body["discovery"]["network"]
            if (previous_network is not None and previous_network["source"] == "NETWORK_PROBE"
                    and (network["source"] != "NETWORK_PROBE"
                         or previous_network["observed_at"] > network["observed_at"])):
                network = dict(previous_network)
                age = now - network["observed_at"]
                network["freshness"] = ("CLOCK_UNCERTAIN" if age < 0 else "FRESH"
                                        if age < network["valid_for_s"] else "STALE")
                if network["freshness"] != "FRESH":
                    network["value"] = "UNKNOWN"
                body["discovery"]["network"] = network
            if "discovery" not in existing:
                related = related_slots(index)
                require(all(records[k]["retention"] == "FREE" for k in related), "DISCOVERY_SLOT_RETAINED")
                protected |= related
            if old["body"] != body:
                change(key, body)
        wanted = {row["reason"] for row in package["image"]["quarantine"] if row is not None}
        for reason in sorted(wanted):
            body = dict(schema_version=1, kind="DISCOVERY_QUARANTINE", reason=reason)
            if any(k.startswith("quarantine.") and r["retention"] == "RETAINED" and r["body"] == body
                   for k, r in records.items()):
                continue
            free = next((k for k, r in records.items() if k.startswith("quarantine.")
                         and r["retention"] == "FREE" and k not in changes), None)
            require(free is not None, "DISCOVERY_QUARANTINE_FULL")
            change(free, body)
        if not changes:
            return "NO_CHANGE"
        plan = RecordMutation.prepare(snapshot, owner=OwnerGuard(self.grant.owner, self.grant.epoch),
                                      changes=changes, protect=protected)
        _, _, handle = self._local()
        package = {**package, "pending": dict(authority=handle.record(), image_revision=package["image"]["revision"],
                                               operation_id=operation, plan=frozen_plan(plan))}
        self._save(package)
        self._current(Action.REGISTER)  # A lost local readback never reaches START.
        report = reconcile(self.leader.backend, plan, mode="START")
        self._finish(package, report)
        return report.outcome

    def _finish(self, package, report):
        if report.outcome in {"CONFIRMED", "SUPERSEDED"} or not report.inspect_required:
            self._save({**package, "pending": None})

    def inspect(self):
        # Read-only reconciliation is allowed after cancellation or loss of role.
        package = self._package(allow_cancelled=True)
        if package["pending"] is None:
            return "NO_WORK"
        plan = restored_plan(package["pending"]["plan"], self.leader.backend.binding)
        report = reconcile(self.leader.backend, plan, mode="INSPECT")
        self._finish(package, report)
        return report.outcome

    def status(self):
        package = self._package(allow_cancelled=True)
        from .network_table import notices
        from .network_table_store import LocalNetworkTable
        value, problem = None, None
        if self.setup._payload.get("network_table") is not None:
            try:
                value = LocalNetworkTable(self.setup).read(allow_pending=True)
            except Exception:
                problem = "NETWORK_TABLE_INSPECT_REQUIRED"
        try:
            sample = self.clock()
            trusted = type(sample) is ClockSample and sample.wall_trusted
            now = sample.utc if trusted else 0
        except Exception:
            trusted, now = False, 0
        if not trusted:
            problem = problem or "NETWORK_CLOCK_UNCERTAIN"
        descriptions = notices(package["image"], value, now=now, clock_trusted=trusted)
        descriptions["problem"] = problem
        return {**Catalogue(package["image"]).status(), "publication_pending": package["pending"] is not None,
                "descriptions": descriptions}
