"""Bounded protected discovery state; observations never enroll a device.

Trusted commissioning supplies Scope and TrustView. They are code inputs, not
capabilities that an untrusted JSON object or device response can grant itself.
Shared publication and actual OS collection are separate adapters.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import ipaddress
import re
from uuid import UUID, uuid4

from .exchange_layout import encoded

METHODS = {"NEIGHBOR_CACHE", "ICMP", "FIXED_HELPER"}
KINDS = {"LAN", "ROUTED", "VPN", "ISOLATED"}
REASONS = {"ADDRESS_IDENTITY_CHANGED", "HINT_COLLISION", "IDENTITY_UNCONFIRMED",
           "VERIFIED_IDENTITY_CONFLICT", "CAPACITY_FULL", "ENDPOINT_CAPACITY"}


class DiscoveryError(ValueError):
    """Closed diagnostic, never includes a name, address or provider output."""


def require(condition, code):
    if not condition:
        raise DiscoveryError(code)


def integer(value, low=0, high=10**12):
    return type(value) is int and low <= value <= high


def identity(value):
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def text(value, maximum=128):
    return (type(value) is str and 0 < len(value) <= maximum
            and value == value.strip() and not any(ord(c) < 32 for c in value))


def address(value):
    try:
        require(type(value) is str and "%" not in value
                and str(ipaddress.ip_address(value)) == value, "DISCOVERY_ADDRESS")
        return ipaddress.ip_address(value)
    except ValueError:
        raise DiscoveryError("DISCOVERY_ADDRESS") from None


@dataclass(frozen=True, repr=False)
class Interface:
    name: str
    index: int
    networks: tuple[str, ...]
    kind: str

    def __post_init__(self):
        require(text(self.name) and integer(self.index, 1, 2**31-1)
                and type(self.kind) is str and self.kind in KINDS and type(self.networks) is tuple
                and 1 <= len(self.networks) <= 32 and all(type(n) is str for n in self.networks),
                "DISCOVERY_INTERFACE")
        require(len(set(self.networks)) == len(self.networks), "DISCOVERY_INTERFACE")
        for network in self.networks:
            try:
                require(type(network) is str and "%" not in network
                        and str(ipaddress.ip_network(network, strict=True)) == network,
                        "DISCOVERY_SCOPE")
            except ValueError:
                raise DiscoveryError("DISCOVERY_SCOPE") from None


@dataclass(frozen=True, repr=False)
class Scope:
    interfaces: tuple[Interface, ...]
    methods: frozenset[str] = frozenset({"NEIGHBOR_CACHE"})
    max_observations: int = 256
    valid_for_s: int = 60

    def __post_init__(self):
        require(type(self.interfaces) is tuple and len(self.interfaces) <= 32
                and all(type(i) is Interface for i in self.interfaces)
                and len({i.index for i in self.interfaces}) == len(self.interfaces)
                and len({i.name for i in self.interfaces}) == len(self.interfaces)
                and type(self.methods) is frozenset and all(type(m) is str for m in self.methods)
                and self.methods <= METHODS
                and integer(self.max_observations, 1, 256)
                and integer(self.valid_for_s, 1, 86400), "DISCOVERY_SCOPE")

    def permits(self, observation):
        if type(observation) is not Observation or observation.source not in self.methods:
            return False
        ip = address(observation.address)
        if ip.is_unspecified or ip.is_multicast or str(ip) == "255.255.255.255":
            return False
        return any(i.index == observation.interface_index
                   and any(ip in (network := ipaddress.ip_network(n))
                           and not (network.version == 4 and network.prefixlen < 31
                                    and ip == network.broadcast_address)
                           for n in i.networks)
                   for i in self.interfaces)


@dataclass(frozen=True, repr=False)
class Observation:
    interface_index: int
    address: str
    source: str
    observed_at: int
    valid_for_s: int
    online: bool = False
    hardware_hint: str | None = None
    name_hint: str | None = None

    def __post_init__(self):
        address(self.address)
        require(integer(self.interface_index, 1, 2**31-1)
                and type(self.source) is str and self.source in METHODS
                and integer(self.observed_at) and integer(self.valid_for_s, 1, 86400)
                and type(self.online) is bool
                and (not self.online or self.source in {"ICMP", "FIXED_HELPER"})
                and all(v is None or text(v) for v in (self.hardware_hint, self.name_hint)),
                "DISCOVERY_OBSERVATION")

    def private(self):
        return dict(interface_index=self.interface_index, address=self.address,
                    source=self.source, observed_at=self.observed_at,
                    valid_for_s=self.valid_for_s, online=self.online,
                    hardware_hint=self.hardware_hint, name_hint=self.name_hint)


@dataclass(frozen=True, repr=False)
class VerifiedBinding:
    """Trusted enrollment adapter's fresh identity proof for one exact endpoint."""
    catalogue_id: str
    interface_index: int
    address: str
    observed_at: int

    def __post_init__(self):
        require(identity(self.catalogue_id) and integer(self.interface_index, 1, 2**31-1)
                and integer(self.observed_at), "DISCOVERY_BINDING")
        address(self.address)


@dataclass(frozen=True, repr=False)
class TrustView:
    # Discovery has no method that adds an identity to this enrollment view.
    enrolled: frozenset[str] = frozenset()
    bindings: tuple[VerifiedBinding, ...] = ()

    def __post_init__(self):
        require(type(self.enrolled) is frozenset and len(self.enrolled) <= 64
                and all(identity(i) for i in self.enrolled)
                and type(self.bindings) is tuple and len(self.bindings) <= 256
                and all(type(b) is VerifiedBinding and b.catalogue_id in self.enrolled
                        for b in self.bindings), "DISCOVERY_TRUST")

    def proven(self, observation):
        if observation.source != "FIXED_HELPER" or not observation.online:
            return None
        found = {b.catalogue_id for b in self.bindings
                 if (b.interface_index, b.address, b.observed_at) ==
                 (observation.interface_index, observation.address, observation.observed_at)}
        require(len(found) <= 1, "DISCOVERY_BINDING_CONFLICT")
        return next(iter(found), None)


def freshness(observation, *, now, clock_trusted=True):
    require(type(observation) is Observation and integer(now)
            and type(clock_trusted) is bool, "DISCOVERY_CLOCK")
    if not clock_trusted or observation.observed_at > now:
        return "CLOCK_UNCERTAIN"
    return "FRESH" if now - observation.observed_at < observation.valid_for_s else "STALE"


def new_image(installation_id, domain_id, *, capacity=8, quarantine_capacity=8):
    require(identity(installation_id) and identity(domain_id)
            and integer(capacity, 1, 64) and integer(quarantine_capacity, 1, 32),
            "DISCOVERY_IMAGE")
    return dict(schema_version=1, installation_id=installation_id, domain_id=domain_id,
                revision=1, entries=[None]*capacity, quarantine=[None]*quarantine_capacity,
                overflow=False)


def validate_image(value, *, installation_id=None, domain_id=None):
    try:
        require(type(value) is dict and set(value) == {
            "schema_version", "installation_id", "domain_id", "revision",
            "entries", "quarantine", "overflow"}, "DISCOVERY_IMAGE")
        require(type(value["schema_version"]) is int and value["schema_version"] == 1
                and identity(value["installation_id"]) and identity(value["domain_id"])
                and (installation_id is None or value["installation_id"] == installation_id)
                and (domain_id is None or value["domain_id"] == domain_id)
                and integer(value["revision"], 1, 2**63-1)
                and type(value["entries"]) is list and 1 <= len(value["entries"]) <= 64
                and type(value["quarantine"]) is list and 1 <= len(value["quarantine"]) <= 32
                and type(value["overflow"]) is bool, "DISCOVERY_IMAGE")
        ids, aliases, endpoints = set(), set(), set()
        for entry in value["entries"]:
            if entry is None:
                continue
            require(type(entry) is dict and set(entry) == {"device_id", "alias", "endpoints"}
                    and identity(entry["device_id"])
                    and type(entry["alias"]) is str
                    and re.fullmatch(r"[a-z][a-z0-9-]{0,31}", entry["alias"])
                    and entry["device_id"] not in ids and entry["alias"] not in aliases
                    and type(entry["endpoints"]) is list and len(entry["endpoints"]) <= 8,
                    "DISCOVERY_ENTRY")
            ids.add(entry["device_id"]); aliases.add(entry["alias"])
            for raw in entry["endpoints"]:
                observation = Observation(**raw)
                endpoint = (observation.interface_index, observation.address)
                require(endpoint not in endpoints, "DISCOVERY_ENDPOINT_COLLISION")
                endpoints.add(endpoint)
        for row in value["quarantine"]:
            if row is not None:
                require(type(row) is dict and set(row) == {"reason", "observation"}
                        and row["reason"] in REASONS, "DISCOVERY_QUARANTINE")
                Observation(**row["observation"])
        require(len(encoded(value)) <= 512*1024, "DISCOVERY_IMAGE_BOUND")
        return copy.deepcopy(value)
    except DiscoveryError:
        raise
    except Exception:
        raise DiscoveryError("DISCOVERY_IMAGE") from None


class Catalogue:
    def __init__(self, image):
        self._image = validate_image(image)

    def private_image(self):
        return copy.deepcopy(self._image)

    def seed(self, slot, device_id, alias):
        """Adopt a trusted pre-existing shared identity; never grants enrollment."""
        require(integer(slot, 0, len(self._image["entries"])-1)
                and self._image["entries"][slot] is None, "DISCOVERY_SLOT")
        value = self.private_image()
        value["entries"][slot] = dict(device_id=device_id, alias=alias, endpoints=[])
        self._replace(value)

    def _replace(self, value):
        require(self._image["revision"] < 2**63-1, "DISCOVERY_REVISION_EXHAUSTED")
        value["revision"] = self._image["revision"] + 1
        self._image = validate_image(value)

    def observe(self, observations, scope, *, now, trust=TrustView(), clock_trusted=True):
        require(type(scope) is Scope and type(trust) is TrustView and integer(now)
                and type(clock_trusted) is bool, "DISCOVERY_CONTEXT")
        require(type(observations) is tuple and len(observations) <= scope.max_observations
                and all(type(o) is Observation for o in observations), "DISCOVERY_BATCH")
        value, outcomes = self.private_image(), []

        def quarantine(reason, observation):
            row = dict(reason=reason, observation=observation.private())
            for index, old in enumerate(value["quarantine"]):
                if (old is not None and old["reason"] == reason
                        and old["observation"]["interface_index"] == observation.interface_index
                        and old["observation"]["address"] == observation.address):
                    if old["observation"]["observed_at"] < observation.observed_at:
                        value["quarantine"][index] = row
                    return reason
            if row not in value["quarantine"]:
                if None in value["quarantine"]:
                    value["quarantine"][value["quarantine"].index(None)] = row
                else:
                    value["overflow"] = True
            return reason

        for observation in observations:
            if not scope.permits(observation):
                outcomes.append("OUT_OF_SCOPE"); continue
            state = freshness(observation, now=now, clock_trusted=clock_trusted)
            if state != "FRESH":
                outcomes.append(state); continue
            require(observation.valid_for_s <= scope.valid_for_s, "DISCOVERY_FRESHNESS_POLICY")
            entries = [e for e in value["entries"] if e is not None]
            endpoint = (observation.interface_index, observation.address)
            owners = [(e, old) for e in entries for old in e["endpoints"]
                      if (old["interface_index"], old["address"]) == endpoint]
            owner, previous = owners[0] if owners else (None, None)
            proven = trust.proven(observation)
            selected = next((e for e in entries if e["device_id"] == proven), None) if proven else None
            if proven and selected is None:
                outcomes.append(quarantine("VERIFIED_IDENTITY_CONFLICT", observation)); continue
            if owner is not None:
                if proven and owner is not selected:
                    outcomes.append(quarantine("VERIFIED_IDENTITY_CONFLICT", observation)); continue
                if not proven and owner["device_id"] in trust.enrolled:
                    outcomes.append(quarantine("IDENTITY_UNCONFIRMED", observation)); continue
                if (not proven and previous["hardware_hint"] is not None
                        and observation.hardware_hint != previous["hardware_hint"]):
                    outcomes.append(quarantine("ADDRESS_IDENTITY_CHANGED", observation)); continue
                if observation.observed_at < previous["observed_at"]:
                    outcomes.append("OLDER_OBSERVATION"); continue
                selected = owner
            if selected is None:
                hints = [e for e in entries for old in e["endpoints"]
                         if observation.hardware_hint is not None
                         and old["hardware_hint"] == observation.hardware_hint]
                if hints:
                    outcomes.append(quarantine("HINT_COLLISION", observation)); continue
                if None not in value["entries"]:
                    outcomes.append(quarantine("CAPACITY_FULL", observation)); continue
                slot = value["entries"].index(None)
                # Random identity is minted once into the protected candidate.
                # The persistence/publication adapter must save before sharing.
                selected = dict(device_id=str(uuid4()), alias=f"device-{slot+1:03d}", endpoints=[])
                if any(e["alias"] == selected["alias"] for e in entries):
                    outcomes.append(quarantine("CAPACITY_FULL", observation)); continue
                value["entries"][slot] = selected
            if previous is None and len(selected["endpoints"]) >= 8:
                outcomes.append(quarantine("ENDPOINT_CAPACITY", observation)); continue
            if previous is not None:
                selected["endpoints"].remove(previous)
            selected["endpoints"].append(observation.private())
            outcomes.append("OBSERVED")
        if value != self._image:
            self._replace(value)
        return tuple(outcomes)

    def shared(self, *, now, trust=TrustView(), clock_trusted=True):
        require(type(trust) is TrustView and integer(now) and type(clock_trusted) is bool,
                "DISCOVERY_CONTEXT")
        result = []
        for slot, entry in enumerate(self._image["entries"]):
            if entry is None:
                continue
            observations = [Observation(**o) for o in entry["endpoints"]]
            latest = max(observations, key=lambda o:o.observed_at) if observations else None
            fresh = freshness(latest, now=now, clock_trusted=clock_trusted) if latest else "UNKNOWN"
            online = bool(latest and latest.online and fresh == "FRESH")
            result.append(dict(slot=slot, device_id=entry["device_id"], alias=entry["alias"],
                trust="ENROLLED" if entry["device_id"] in trust.enrolled else "UNTRUSTED",
                network=dict(value="ONLINE" if online else "UNKNOWN",
                             source="NETWORK_PROBE" if latest and latest.online else "NONE",
                             observed_at=latest.observed_at if latest and latest.online else None,
                             valid_for_s=latest.valid_for_s if latest and latest.online else None,
                             freshness=fresh)))
        return tuple(result)

    def status(self):
        return dict(used=sum(e is not None for e in self._image["entries"]),
                    capacity=len(self._image["entries"]),
                    quarantined=sum(e is not None for e in self._image["quarantine"]),
                    quarantine_capacity=len(self._image["quarantine"]),
                    overflow=self._image["overflow"], automatic_enrollment=False)
