"""Closed protected discovery package, embedded in the existing setup frame."""
from __future__ import annotations

import copy
from dataclasses import asdict
import ipaddress
import json
import re

from .discovery_catalogue import (DiscoveryError, Interface, Scope, REASONS,
                                integer, identity, require, validate_image)
from .drive.commissioning import restored_plan
from .exchange_layout import empty_document, encoded, validate_document


def scope_record(scope):
    require(type(scope) is Scope, "DISCOVERY_SCOPE")
    return dict(interfaces=[{**asdict(i), "networks": list(i.networks)} for i in scope.interfaces],
                methods=sorted(scope.methods), max_observations=scope.max_observations,
                valid_for_s=scope.valid_for_s)


def parse_scope(value):
    try:
        require(type(value) is dict and set(value) == {
            "interfaces", "methods", "max_observations", "valid_for_s"}
            and type(value["interfaces"]) is list and len(value["interfaces"]) <= 32
            and type(value["methods"]) is list and len(value["methods"]) <= 3
            and all(type(m) is str for m in value["methods"])
            and len(set(value["methods"])) == len(value["methods"]), "DISCOVERY_SCOPE")
        interfaces = []
        for row in value["interfaces"]:
            require(type(row) is dict and set(row) == {"name", "index", "networks", "kind"}
                    and type(row["networks"]) is list, "DISCOVERY_SCOPE")
            interfaces.append(Interface(**{**row, "networks": tuple(row["networks"])}))
        return Scope(tuple(interfaces), frozenset(value["methods"]),
                     value["max_observations"], value["valid_for_s"])
    except DiscoveryError:
        raise
    except Exception:
        raise DiscoveryError("DISCOVERY_SCOPE") from None


def catalogue_body(value):
    """Allowlisted shared schema. Trust is an informational projection, no grant."""
    require(type(value) is dict and set(value) == {
        "schema_version", "kind", "device_id", "alias", "trust", "network"}
        and type(value["schema_version"]) is int and value["schema_version"] == 1
        and value["kind"] == "DISCOVERY" and identity(value["device_id"])
        and type(value["alias"]) is str and re.fullmatch(r"[a-z][a-z0-9-]{0,31}", value["alias"])
        and value["trust"] in {"ENROLLED", "UNTRUSTED"}, "DISCOVERY_FOREIGN_CATALOGUE")
    network = value["network"]
    require(type(network) is dict and set(network) == {
        "value", "source", "observed_at", "valid_for_s", "freshness"}
        and network["value"] in {"ONLINE", "UNKNOWN"}
        and network["source"] in {"NETWORK_PROBE", "NONE"}
        and network["freshness"] in {"FRESH", "STALE", "CLOCK_UNCERTAIN", "UNKNOWN"},
        "DISCOVERY_FOREIGN_CATALOGUE")
    if network["source"] == "NONE":
        require(network["value"] == "UNKNOWN" and network["observed_at"] is None
                and network["valid_for_s"] is None, "DISCOVERY_FOREIGN_CATALOGUE")
    else:
        require(integer(network["observed_at"]) and integer(network["valid_for_s"], 1, 86400)
                and (network["value"] != "ONLINE" or network["freshness"] == "FRESH"),
                "DISCOVERY_FOREIGN_CATALOGUE")
    return value


def quarantine_body(value):
    require(type(value) is dict and set(value) == {"schema_version", "kind", "reason"}
            and type(value["schema_version"]) is int and value["schema_version"] == 1
            and value["kind"] == "DISCOVERY_QUARANTINE"
            and type(value["reason"]) is str and value["reason"] in REASONS,
            "DISCOVERY_QUARANTINE")
    return value


def catalogue_record(row):
    # RP019 owns these artifact bindings and enrollment seed. Discovery adds one
    # nested projection without replacing either field or interpreting it as trust.
    body = row["body"]
    require(row["retention"] == "RETAINED" and type(body) is dict
            and {"artifacts", "enrollment"} <= set(body)
            and set(body) <= {"artifacts", "enrollment", "discovery", "ballpark", "fetcher"}
            and type(body["artifacts"]) is dict
            and set(body["artifacts"]) == {"input", "output"}, "DISCOVERY_FOREIGN_CATALOGUE")
    from .drive.commissioning import Allocation
    for ref in body["artifacts"].values():
        require(type(ref) is dict and set(ref) == {"id", "seal"}, "DISCOVERY_FOREIGN_CATALOGUE")
        allocation = Allocation(ref["id"], "0"*64, seal=ref["seal"])
        require(allocation.seal is not None, "DISCOVERY_FOREIGN_CATALOGUE")
    if "discovery" in body:
        catalogue_body(body["discovery"])
    if "ballpark" in body:
        from .ballpark_records import expand
        require("discovery" in body, "DISCOVERY_FOREIGN_CATALOGUE")
        expand(body["ballpark"], body["discovery"])
    from .enrollment_records import validate_extension
    validate_extension(body)
    return body


def related_slots(index):
    return {f"target.{index:03d}.{k}" for k in ("work", "result", "cancel", "ack", "status")} | {
        f"artifact.{index:03d}.{k}" for k in ("input", "output")}


def validated_package(value, *, installation, spec, authority, networks):
    try:
        require(type(value) is dict and set(value) == {"schema_version", "scope", "image", "pending"}
                and type(value["schema_version"]) is int and value["schema_version"] == 1,
                "DISCOVERY_PACKAGE")
        scope = parse_scope(value["scope"])
        require(type(networks) is list, "DISCOVERY_SCOPE_NOT_SELECTED")
        permitted = [ipaddress.ip_network(n) for n in networks]
        for interface in scope.interfaces:
            for raw in interface.networks:
                net = ipaddress.ip_network(raw)
                require(any(net.version == allowed.version and net.subnet_of(allowed)
                            for allowed in permitted), "DISCOVERY_SCOPE_NOT_AUTHORIZED")
        image = validate_image(value["image"], installation_id=installation, domain_id=spec.domain_id)
        require(len(image["entries"]) == spec.capacity.devices
                and len(image["quarantine"]) == spec.capacity.quarantine, "DISCOVERY_CAPACITY")
        pending = value["pending"]
        if pending is not None:
            require(type(pending) is dict and set(pending) == {
                "authority", "image_revision", "operation_id", "plan"}
                and pending["authority"] == authority.record()
                and pending["image_revision"] == image["revision"]
                and type(pending["operation_id"]) is str
                and re.fullmatch(r"[0-9a-f]{64}", pending["operation_id"]), "DISCOVERY_PENDING")
            plan = restored_plan(pending["plan"], None)
            require(plan.owner.owner == installation and integer(plan.owner.epoch, 1, 2**63-1),
                    "DISCOVERY_PENDING")
            header, protected, before, after = [json.loads(getattr(plan, k))
                                               for k in ("header", "protected", "before", "after")]
            for key, raw in zip(("header", "protected", "before", "after"), (header, protected, before, after)):
                require(encoded(raw) == getattr(plan, key), "DISCOVERY_PENDING")
            document = empty_document(spec.domain_id, spec.capacity)
            require(header == {k: v for k, v in document.items() if k != "records"}
                    and type(before) is dict and type(after) is dict and before
                    and before.keys() == after.keys() and type(protected) is dict,
                    "DISCOVERY_PENDING")
            required = {"global.commissioning"}
            for key, row in after.items():
                require(type(key) is str and key in document["records"], "DISCOVERY_PENDING")
                if re.fullmatch(r"target\.[0-9]{3}\.catalogue", key):
                    index = int(key.split(".")[1])
                    full = catalogue_record(row)
                    old = catalogue_record(before[key])
                    require({k:v for k,v in full.items() if k != "discovery"} ==
                            {k:v for k,v in old.items() if k != "discovery"}, "DISCOVERY_PENDING")
                    body = catalogue_body(full["discovery"])
                    entry = image["entries"][index]
                    require(entry is not None and all(body[k] == entry[k] for k in ("device_id", "alias")),
                            "DISCOVERY_PENDING")
                    if "discovery" not in old:
                        required |= related_slots(index)
                        require(all(protected[k]["retention"] == "FREE" for k in related_slots(index)),
                                "DISCOVERY_PENDING")
                    else:
                        require(all(body[k] == old["discovery"][k] for k in ("device_id", "alias")),
                                "DISCOVERY_PENDING")
                elif re.fullmatch(r"quarantine\.[0-9]{3}", key):
                    quarantine_body(row["body"])
                    require(before[key]["retention"] == "FREE", "DISCOVERY_PENDING")
                else:
                    raise DiscoveryError("DISCOVERY_PENDING")
                require(row["retention"] == "RETAINED"
                        and row["operation_id"] == pending["operation_id"]
                        and row["generation"] == before[key]["generation"] + 1, "DISCOVERY_PENDING")
            require(set(protected) == required and protected["global.commissioning"] == dict(
                generation=0, operation_id=spec.setup_id, retention="RETAINED",
                body=spec.marker("STORAGE_READY")), "DISCOVERY_PENDING")
            document["records"].update(protected)
            document["records"].update(before)
            validate_document(document)
            document["records"].update(after)
            validate_document(document)
        return copy.deepcopy(value)
    except DiscoveryError:
        raise
    except Exception:
        raise DiscoveryError("DISCOVERY_PACKAGE") from None
