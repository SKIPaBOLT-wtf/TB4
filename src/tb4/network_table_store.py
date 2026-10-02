"""Local table transactions: durable intent, exact native readback, no blind replay."""
from __future__ import annotations

import copy
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import secrets
from uuid import uuid4

from .commissioning_state import Setup, storage_spec
from .discovery_catalogue import new_image, identity, integer
from .network_table import (AddressingObservation, endpoint_digest, new_table, validate, proposal,
                            notices, require, NetworkTableError)
from .private_settings import PrivateSettings, native_settings, encoded, SettingsError


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def path(value):
    require(type(value) is str and 0 < len(value) <= 4096 and value == value.strip()
            and not any(ord(c) < 32 for c in value), "NETWORK_LOCATION")
    result = Path(value)
    require(result.is_absolute() and result != result.anchor and ".." not in result.parts
            and result.parent != result, "NETWORK_LOCATION")
    return result


def selection(value, payload):
    """Closed optional extension of the protected commissioning frame."""
    require(type(value) is dict and set(value) == {
        "schema_version", "table_id", "domain_id", "root", "binding_digest", "pending"},
        "NETWORK_SELECTION")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1
            and identity(value["table_id"]) and identity(value["domain_id"])
            and payload["choices"]["role"] == "watchdog", "NETWORK_SELECTION")
    spec, _ = storage_spec(payload["choices"]["storage"])
    require(value["domain_id"] == spec.domain_id, "NETWORK_SELECTION_IDENTITY")
    if value["root"] is not None:
        path(value["root"])
        require(type(value["binding_digest"]) is str and len(value["binding_digest"]) == 64
                and all(c in "0123456789abcdef" for c in value["binding_digest"]), "NETWORK_SELECTION")
    else:
        require(value["binding_digest"] is None, "NETWORK_SELECTION")
    pending = value["pending"]
    require(value["root"] is not None or pending is not None, "NETWORK_SELECTION")
    if pending is not None:
        require(type(pending) is dict and set(pending) == {
            "kind", "operation_id", "target_root", "source_revision", "source_digest", "candidate", "requires_owner"},
            "NETWORK_TRANSACTION")
        require(pending["kind"] in {"CREATE", "MOVE", "UPDATE"}
                and type(pending["requires_owner"]) is bool
                and type(pending["operation_id"]) is str and len(pending["operation_id"]) == 64
                and all(c in "0123456789abcdef" for c in pending["operation_id"]),
                "NETWORK_TRANSACTION")
        path(pending["target_root"])
        validate(pending["candidate"], installation=payload["installation_id"],
                 domain=value["domain_id"], table_id=value["table_id"])
        if pending["kind"] == "CREATE":
            require(value["root"] is None and type(pending["source_revision"]) is int
                    and pending["source_revision"] == 0
                    and pending["source_digest"] is None, "NETWORK_TRANSACTION")
        else:
            require(value["root"] is not None and integer(pending["source_revision"], 1, 2**63-1)
                    and type(pending["source_digest"]) is str
                    and len(pending["source_digest"]) == 64
                    and all(c in "0123456789abcdef" for c in pending["source_digest"]),
                    "NETWORK_TRANSACTION")
            require((pending["kind"] == "UPDATE") ==
                    (pending["target_root"] == value["root"]), "NETWORK_TRANSACTION")
    encoded(value)
    return copy.deepcopy(value)


class LocalNetworkTable:
    def __init__(self, setup, *, installation_root=None, factory=None):
        factory = factory or native_settings
        require(type(setup) is Setup and callable(factory), "NETWORK_CONTEXT")
        require(installation_root is None or isinstance(installation_root, Path)
                and installation_root.is_absolute(), "NETWORK_LOCATION")
        self.setup, self.installation_root, self.factory = setup, installation_root, factory

    def _selected(self):
        self.setup._fresh()
        value = self.setup._payload.get("network_table")
        require(value is not None, "NETWORK_TABLE_NOT_CONFIGURED")
        return selection(value, self.setup._payload)

    def _save_selection(self, value):
        self.setup._fresh()
        self.setup._save({**self.setup._payload, "network_table": value})

    @contextmanager
    def _setup_lock(self):
        """Hold the native settings lock through a table mutation, including freshness."""
        try:
            with self.setup.store.native.locked() as port:
                raw = port.read("settings.json")
                current = self.setup.store._decode(raw, port.binding)
                require(port.read("settings.pending") is None
                        and current.revision == self.setup.snapshot.revision
                        and current.payload == self.setup._payload, "NETWORK_SETTINGS_CHANGED")
                yield
        except NetworkTableError:
            raise
        except Exception:
            raise NetworkTableError("NETWORK_SETTINGS_UNAVAILABLE") from None

    def _store(self, root, *, create=False):
        try:
            store = self.factory(path(root), create=create, owner_authorized=create)
            require(type(store) is PrivateSettings, "NETWORK_STORE")
            return store
        except NetworkTableError:
            raise
        except Exception:
            raise NetworkTableError("NETWORK_STORE_UNAVAILABLE") from None

    def _binding(self, store):
        with store.native.locked() as port:
            return digest(port.binding)

    def _read_store(self, store, selected):
        try:
            snapshot = store.read()
            require(snapshot is not None, "NETWORK_TABLE_MISSING")
            validate(snapshot.payload, installation=self.setup.installation_id,
                     domain=selected["domain_id"], table_id=selected["table_id"])
            return snapshot
        except NetworkTableError:
            raise
        except Exception:
            raise NetworkTableError("NETWORK_TABLE_INSPECT_REQUIRED") from None

    def read(self, *, allow_pending=False):
        selected = self._selected()
        require(allow_pending or selected["pending"] is None, "NETWORK_TABLE_INSPECT_REQUIRED")
        require(selected["root"] is not None, "NETWORK_TABLE_NOT_CONFIGURED")
        store = self._store(selected["root"])
        require(self._binding(store) == selected["binding_digest"], "NETWORK_LOCATION_CHANGED")
        return self._read_store(store, selected).payload

    def local_location(self):
        """Only local UI; never include this path in a report/assistance request."""
        selected = self.setup._payload.get("network_table")
        if selected is not None:
            return selected["root"] or selected["pending"]["target_root"]
        require(self.installation_root is not None, "NETWORK_INSTALLATION_LOCATION_REQUIRED")
        return str(self.installation_root / "network-table")

    def _maintenance(self, authorized):
        self.setup._fresh()
        require(authorized is True and self.setup.private_choices()["role"] == "watchdog",
                "NETWORK_OWNER_APPROVAL_REQUIRED")
        require(self.setup._payload["state"] != "CANCELLED", "NETWORK_SETUP_CANCELLED")
        require("UNKNOWN" not in self.setup._payload["operations"].values(), "NETWORK_SETUP_INSPECT_REQUIRED")

    def configure(self, root=None, *, owner_authorized=False):
        self._maintenance(owner_authorized)
        require(self.setup._payload.get("network_table") is None, "NETWORK_TABLE_ALREADY_CONFIGURED")
        target = str(path(str(root) if root is not None else self.local_location()))
        require(not os.path.lexists(target), "NETWORK_DESTINATION_EXISTS")
        spec, _ = storage_spec(self.setup.private_choices()["storage"])
        discovery = self.setup._payload.get("discovery")
        image = (discovery["image"] if discovery is not None else
                 new_image(self.setup.installation_id, spec.domain_id,
                           capacity=spec.capacity.devices, quarantine_capacity=spec.capacity.quarantine))
        table_id = str(uuid4())
        value = dict(schema_version=1, table_id=table_id, domain_id=spec.domain_id,
                     root=None, binding_digest=None, pending=dict(
                         kind="CREATE", operation_id=secrets.token_hex(32), target_root=target,
                         source_revision=0, source_digest=None, candidate=new_table(image, table_id), requires_owner=False))
        self._save_selection(value)  # Before exclusive native directory creation.
        return self.resume(owner_authorized=True)

    def move(self, root, *, owner_authorized=False):
        self._maintenance(owner_authorized)
        selected = self._selected()
        require(selected["pending"] is None, "NETWORK_TABLE_INSPECT_REQUIRED")
        target = str(path(str(root)))
        require(target != selected["root"] and not os.path.lexists(target), "NETWORK_DESTINATION_EXISTS")
        store = self._store(selected["root"])
        require(self._binding(store) == selected["binding_digest"], "NETWORK_LOCATION_CHANGED")
        before = self._read_store(store, selected)
        self._save_selection({**selected, "pending": dict(
            kind="MOVE", operation_id=secrets.token_hex(32), target_root=target,
            source_revision=before.revision, source_digest=digest(before.payload),
            candidate=before.payload, requires_owner=False)})
        return self.resume(owner_authorized=True)

    def _update(self, candidate, *, current_owner=None):
        selected = self._selected()
        require(selected["pending"] is None, "NETWORK_TABLE_INSPECT_REQUIRED")
        store = self._store(selected["root"])
        require(self._binding(store) == selected["binding_digest"], "NETWORK_LOCATION_CHANGED")
        before = self._read_store(store, selected)
        candidate = validate(candidate, installation=self.setup.installation_id,
                             domain=selected["domain_id"], table_id=selected["table_id"])
        require(candidate["revision"] == before.payload["revision"] + 1, "NETWORK_REVISION_CHANGED")
        self._save_selection({**selected, "pending": dict(
            kind="UPDATE", operation_id=secrets.token_hex(32), target_root=selected["root"],
            source_revision=before.revision, source_digest=digest(before.payload), candidate=candidate,
            requires_owner=current_owner is not None)})
        return self.resume(owner_authorized=True, current_owner=current_owner)

    def _target(self, selected, *, write, current_owner):
        pending = selected["pending"]
        def guard():
            if pending["requires_owner"]:
                require(callable(current_owner) and current_owner() is True, "NETWORK_OWNER_SUPERSEDED")
        target = pending["target_root"]
        exists = os.path.lexists(target)
        require(exists or write, "NETWORK_DESTINATION_NOT_CREATED")
        if not exists:
            guard()
        store = self._store(target, create=not exists)
        # Inspect an exact staged native candidate before any recovery promotion.
        with store.native.locked() as port:
            staged = port.read("settings.pending")
            if staged is not None:
                candidate = store._decode(staged, port.binding)
                require(candidate.payload == pending["candidate"], "NETWORK_DESTINATION_CONFLICT")
        if staged is not None:
            guard()
        current = store.recover_pending() if staged is not None else store.read()
        if current is not None and current.payload == pending["candidate"]:
            return store, current
        if pending["kind"] == "UPDATE":
            require(current is not None and current.revision == pending["source_revision"]
                    and digest(current.payload) == pending["source_digest"], "NETWORK_SOURCE_CHANGED")
        else:
            # An existing empty directory has no proof it was our interrupted mkdir.
            require(not exists and current is None, "NETWORK_DESTINATION_CONFLICT")
        require(write, "NETWORK_NOT_APPLIED")
        guard()
        current = store.save(pending["candidate"],
                             expected_revision=pending["source_revision"] if pending["kind"] == "UPDATE" else 0)
        require(current.payload == pending["candidate"], "NETWORK_READBACK_UNCONFIRMED")
        return store, current

    def _finish(self, *, write, current_owner=None):
        selected = self._selected()
        require(selected["pending"] is not None, "NETWORK_NO_PENDING_TRANSACTION")
        pending = selected["pending"]
        try:
            with self._setup_lock():
                if pending["kind"] == "MOVE":
                    source = self._store(selected["root"])
                    require(self._binding(source) == selected["binding_digest"], "NETWORK_LOCATION_CHANGED")
                    before = self._read_store(source, selected)
                    require(before.revision == pending["source_revision"]
                            and digest(before.payload) == pending["source_digest"], "NETWORK_SOURCE_CHANGED")
                target, current = self._target(selected, write=write, current_owner=current_owner)
                validate(current.payload, installation=self.setup.installation_id,
                         domain=selected["domain_id"], table_id=selected["table_id"])
                binding = self._binding(target)
            # Source selection and the whole exact pending operation stay durable
            # until target readback. Other trusted writers see pending and stop.
            self._save_selection({**selected, "root": pending["target_root"],
                                  "binding_digest": binding, "pending": None})
            return "CONFIRMED"
        except NetworkTableError:
            raise
        except Exception:
            raise NetworkTableError("NETWORK_TRANSACTION_UNCONFIRMED") from None

    def inspect(self, *, current_owner=None):
        """Reconcile only an exact completed/staged candidate; never recreate it."""
        return self._finish(write=False, current_owner=current_owner)

    def resume(self, *, owner_authorized=False, current_owner=None):
        self._maintenance(owner_authorized)
        return self._finish(write=True, current_owner=current_owner)

    def sync_observations(self, image, *, current_owner):
        """Discovery supplies a fresh code callback; no probing/configuration here."""
        require(callable(current_owner), "NETWORK_OBSERVATION_CONTEXT")
        value = self.read()
        from .discovery_catalogue import validate_image
        image = validate_image(image, installation_id=value["installation_id"], domain_id=value["domain_id"])
        require(len(image["entries"]) == len(value["catalogue"]["entries"])
                and image["revision"] >= value["catalogue"]["revision"], "NETWORK_OBSERVATION_REVISION")
        old = {e["device_id"]:e["alias"] for e in value["catalogue"]["entries"] if e is not None}
        new = {e["device_id"]:e["alias"] for e in image["entries"] if e is not None}
        require(all(new.get(k) == v for k,v in old.items()), "NETWORK_OBSERVATION_IDENTITY")
        if image == value["catalogue"]:
            return "NO_CHANGE"
        require(current_owner() is True, "NETWORK_OWNER_SUPERSEDED")
        return self._update({**value, "revision":value["revision"]+1, "catalogue":image}, current_owner=current_owner)

    def approve(self, proposed, *, now, valid_for_s=31536000, owner_authorized=False,
                instruction_commit=None):
        self._maintenance(owner_authorized)
        proposed = proposal(proposed)
        value = self.read()
        require(proposed["expected_revision"] == value["revision"], "NETWORK_REVISION_CHANGED")
        device_id = proposed["device_id"]
        entry = next((e for e in value["catalogue"]["entries"]
                      if e is not None and e["device_id"] == device_id), None)
        require(entry is not None and integer(now) and integer(valid_for_s, 1, 31536000),
                "NETWORK_DESCRIPTION_APPROVAL")
        row = dict(description=proposed["description"], approved_at=now, valid_for_s=valid_for_s,
                   source="OWNER_LOCAL" if instruction_commit is None else "REPOSITORY_SKILL",
                   instruction_commit=instruction_commit)
        value["descriptions"][device_id] = row
        # This is explicitly the owner's reported assignment, never verified DHCP.
        value["addressing"][device_id] = dict(
            value=proposed["description"]["stable_ip"], source="OWNER_DECLARATION",
            observed_at=now, valid_for_s=valid_for_s, endpoint_digest=endpoint_digest(entry))
        value["revision"] += 1
        return self._update(value)

    def record_addressing(self, observation, *, current_owner):
        require(type(observation) is AddressingObservation and callable(current_owner),
                "NETWORK_ADDRESSING_CONTEXT")
        value = self.read()
        entry = next((e for e in value["catalogue"]["entries"]
                      if e is not None and e["device_id"] == observation.device_id), None)
        require(entry is not None and observation.endpoint_digest == endpoint_digest(entry)
                and current_owner() is True, "NETWORK_ADDRESSING_IDENTITY")
        value["addressing"][observation.device_id] = dict(
            value=observation.value, source="FIXED_HELPER", observed_at=observation.observed_at,
            valid_for_s=observation.valid_for_s, endpoint_digest=observation.endpoint_digest)
        value["revision"] += 1
        return self._update(value, current_owner=current_owner)

    def status(self, *, now, image=None):
        if image is None:
            discovery = self.setup._payload.get("discovery")
            image = discovery["image"] if discovery is not None else self.read(allow_pending=True)["catalogue"]
        value = self.read(allow_pending=True)
        result = notices(image, value, now=now)
        result["maintenance"] = "INSPECT_REQUIRED" if self._selected()["pending"] is not None else "NONE"
        return result

