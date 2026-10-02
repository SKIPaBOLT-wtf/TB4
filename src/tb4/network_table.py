"""Closed local network facts. Description and addressing never grant execution."""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import re

from jsonschema import Draft202012Validator

from .discovery_catalogue import validate_image, identity, integer
from .private_settings import encoded, unique
from .privacy import closed

DEVICE_KINDS = ("COMPUTER", "ROUTER", "SWITCH", "ACCESS_POINT", "PRINTER", "STORAGE", "OTHER", "UNKNOWN")
CAPABILITIES = ("ssh_status", "ssh_start", "wake", "fetcher_execution")
GUIDANCE = "skill/tb4/operations/device-description/SKILL.md"
PLATFORM = closed({"os": {"enum": ["WINDOWS", "LINUX", "OTHER", "UNKNOWN"]},
                   "architecture": {"enum": ["X64", "ARM64", "X86", "OTHER", "UNKNOWN"]}})
DESCRIPTION_SCHEMA = closed({
    "device_kind": {"enum": list(DEVICE_KINDS)}, "platform": PLATFORM,
    "roles": {"type": "array", "maxItems": 2, "uniqueItems": True,
              "items": {"enum": ["watchdog", "fetcher"]}},
    "launch_mode": {"type": "object", "propertyNames": {"enum": ["watchdog", "fetcher"]},
                    "additionalProperties": {"enum": ["DESKTOP_SESSION", "OS_SERVICE", "EXTERNAL", "UNSUPPORTED"]}},
    "transports": {"type": "array", "maxItems": 4, "uniqueItems": True,
                   "items": {"enum": ["DRIVE_API", "SHARED_FOLDER", "SSH", "WOL"]}},
    "capabilities": closed({k: {"enum": ["SUPPORTED", "UNSUPPORTED", "UNKNOWN"]} for k in CAPABILITIES}),
    "stable_ip": {"enum": ["ASSIGNED", "NOT_ASSIGNED", "UNKNOWN"]},
})
PROPOSAL_SCHEMA = closed({
    "schema_version": {"const": 1},
    "expected_revision": {"type": "integer", "minimum": 1, "maximum": 2**63-1},
    "device_id": {"type": "string", "pattern": "^[0-9a-f-]{36}$"},
    "description": DESCRIPTION_SCHEMA,
})
SCHEMA_BUNDLE = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                 "$defs": {"description": DESCRIPTION_SCHEMA, "proposal": PROPOSAL_SCHEMA},
                 "$ref": "#/$defs/proposal"}

ID = {"type":"string", "pattern":"^[0-9a-f-]{36}$"}
NUMBER = {"type":"integer", "minimum":0, "maximum":10**12}
TTL = {"type":"integer", "minimum":1, "maximum":31536000}
OBSERVATION_SCHEMA = closed({
    "interface_index":{"type":"integer", "minimum":1, "maximum":2**31-1},
    "address":{"type":"string", "maxLength":64},
    "source":{"enum":["NEIGHBOR_CACHE","ICMP","FIXED_HELPER"]},
    "observed_at":NUMBER, "valid_for_s":{"type":"integer","minimum":1,"maximum":86400},
    "online":{"type":"boolean"},
    "hardware_hint":{"type":["string","null"],"maxLength":128},
    "name_hint":{"type":["string","null"],"maxLength":128},
})
ENTRY_SCHEMA = closed({"device_id":ID, "alias":{"type":"string","pattern":"^[a-z][a-z0-9-]{0,31}$"},
                       "endpoints":{"type":"array","maxItems":8,"items":OBSERVATION_SCHEMA}})
IMAGE_SCHEMA = closed({
    "schema_version":{"const":1},"installation_id":ID,"domain_id":ID,
    "revision":{"type":"integer","minimum":1,"maximum":2**63-1},
    "entries":{"type":"array","minItems":1,"maxItems":64,
               "items":{"oneOf":[{"type":"null"},ENTRY_SCHEMA]}},
    "quarantine":{"type":"array","minItems":1,"maxItems":32,
                  "items":{"oneOf":[{"type":"null"},closed({
                      "reason":{"enum":["ADDRESS_IDENTITY_CHANGED","HINT_COLLISION","IDENTITY_UNCONFIRMED",
                                         "VERIFIED_IDENTITY_CONFLICT","CAPACITY_FULL","ENDPOINT_CAPACITY"]},
                      "observation":OBSERVATION_SCHEMA})]}},
    "overflow":{"type":"boolean"},
})
APPROVAL_SCHEMA = closed({
    "description":DESCRIPTION_SCHEMA,"approved_at":NUMBER,"valid_for_s":TTL,
    "source":{"enum":["OWNER_LOCAL","REPOSITORY_SKILL"]},
    "instruction_commit":{"type":["string","null"],"pattern":"^[0-9a-f]{40}$"},
})
ADDRESSING_SCHEMA = closed({
    "value":{"enum":["ASSIGNED","NOT_ASSIGNED","UNKNOWN"]},
    "source":{"enum":["OWNER_DECLARATION","FIXED_HELPER","NONE"]},
    "observed_at":{"type":["integer","null"],"minimum":0,"maximum":10**12},
    "valid_for_s":{"type":["integer","null"],"minimum":1,"maximum":31536000},
    "endpoint_digest":{"type":"string","pattern":"^[0-9a-f]{64}$"},
})
TABLE_SCHEMA = closed({
    "schema_version":{"const":1},"kind":{"const":"NETWORK_TABLE"},
    "visibility":{"const":"PROTECTED_LOCAL"},"table_id":ID,"installation_id":ID,"domain_id":ID,
    "revision":{"type":"integer","minimum":1,"maximum":2**63-1},"catalogue":IMAGE_SCHEMA,
    "descriptions":{"type":"object","maxProperties":64,"propertyNames":ID,"additionalProperties":APPROVAL_SCHEMA},
    "addressing":{"type":"object","maxProperties":64,"propertyNames":ID,"additionalProperties":ADDRESSING_SCHEMA},
})
TABLE_SCHEMA_BUNDLE = {"$schema":"https://json-schema.org/draft/2020-12/schema",**TABLE_SCHEMA}


class NetworkTableError(ValueError):
    """Only closed diagnostics; never echo private input/provider exceptions."""


def require(condition, code):
    if not condition:
        raise NetworkTableError(code)


def shape(value, schema):
    try:
        require(not next(Draft202012Validator(schema).iter_errors(value), None), "NETWORK_DESCRIPTION_SCHEMA")
    except NetworkTableError:
        raise
    except Exception:
        raise NetworkTableError("NETWORK_DESCRIPTION_SCHEMA") from None


def description(value):
    shape(value, DESCRIPTION_SCHEMA)
    require(set(value["launch_mode"]) == set(value["roles"]), "NETWORK_DESCRIPTION_ROLES")
    return copy.deepcopy(value)


def proposal(value):
    shape(value, PROPOSAL_SCHEMA)
    require(type(value["schema_version"]) is int and value["schema_version"] == 1
            and integer(value["expected_revision"], 1, 2**63-1) and identity(value["device_id"]),
            "NETWORK_PROPOSAL")
    description(value["description"])
    return copy.deepcopy(value)


def parse_proposal(raw):
    try:
        require(type(raw) is bytes and 0 < len(raw) <= 16384, "NETWORK_PROPOSAL_BOUND")
        return proposal(json.loads(raw, object_pairs_hook=unique,
                                   parse_constant=lambda _: require(False, "NETWORK_PROPOSAL")))
    except NetworkTableError:
        raise
    except Exception:
        raise NetworkTableError("NETWORK_PROPOSAL") from None


def render_proposal(value):
    return encoded(proposal(value))


def missing_fields(value):
    value = description(value)
    missing = []
    if value["device_kind"] == "UNKNOWN":
        missing.append("device_kind")
    if value["roles"]:
        if value["device_kind"] != "COMPUTER":
            missing.append("device_kind_for_role")
        for name, item in value["platform"].items():
            if item == "UNKNOWN":
                missing.append("platform." + name)
    # Unknown addressing/capabilities are truthful declarations, not incompleteness.
    return sorted(missing)


def endpoint_digest(entry):
    return hashlib.sha256(encoded(sorted(
        [[o["interface_index"], o["address"]] for o in entry["endpoints"]]))).hexdigest()


def validate(value, *, installation=None, domain=None, table_id=None):
    try:
        shape(value, TABLE_SCHEMA)
        require(type(value) is dict and set(value) == {
            "schema_version", "kind", "visibility", "table_id", "installation_id", "domain_id",
            "revision", "catalogue", "descriptions", "addressing"}, "NETWORK_TABLE_SCHEMA")
        require(type(value["schema_version"]) is int and value["schema_version"] == 1
                and value["kind"] == "NETWORK_TABLE" and value["visibility"] == "PROTECTED_LOCAL"
                and all(identity(value[k]) for k in ("table_id", "installation_id", "domain_id"))
                and integer(value["revision"], 1, 2**63-1), "NETWORK_TABLE_SCHEMA")
        require((installation is None or value["installation_id"] == installation)
                and (domain is None or value["domain_id"] == domain)
                and (table_id is None or value["table_id"] == table_id), "NETWORK_TABLE_IDENTITY")
        image = validate_image(value["catalogue"], installation_id=value["installation_id"],
                               domain_id=value["domain_id"])
        ids = {e["device_id"] for e in image["entries"] if e is not None}
        for key in ("descriptions", "addressing"):
            require(type(value[key]) is dict and set(value[key]) <= ids, "NETWORK_TABLE_BINDING")
        for row in value["descriptions"].values():
            require(type(row) is dict and set(row) == {
                "description", "approved_at", "valid_for_s", "source", "instruction_commit"},
                "NETWORK_DESCRIPTION_APPROVAL")
            description(row["description"])
            require(integer(row["approved_at"]) and integer(row["valid_for_s"], 1, 31536000)
                    and row["source"] in {"OWNER_LOCAL", "REPOSITORY_SKILL"}, "NETWORK_DESCRIPTION_APPROVAL")
            require((row["source"] == "OWNER_LOCAL" and row["instruction_commit"] is None)
                    or (row["source"] == "REPOSITORY_SKILL" and type(row["instruction_commit"]) is str
                        and re.fullmatch("[0-9a-f]{40}", row["instruction_commit"])), "NETWORK_DESCRIPTION_APPROVAL")
        for row in value["addressing"].values():
            require(type(row) is dict and set(row) == {
                "value", "source", "observed_at", "valid_for_s", "endpoint_digest"},
                "NETWORK_ADDRESSING")
            require(row["value"] in {"ASSIGNED", "NOT_ASSIGNED", "UNKNOWN"}
                    and row["source"] in {"OWNER_DECLARATION", "FIXED_HELPER", "NONE"}
                    and type(row["endpoint_digest"]) is str
                    and re.fullmatch("[0-9a-f]{64}", row["endpoint_digest"]), "NETWORK_ADDRESSING")
            if row["source"] == "NONE":
                require(row["value"] == "UNKNOWN" and row["observed_at"] is None
                        and row["valid_for_s"] is None, "NETWORK_ADDRESSING")
            else:
                require(integer(row["observed_at"]) and integer(row["valid_for_s"], 1, 31536000),
                        "NETWORK_ADDRESSING")
        encoded(value)
        return copy.deepcopy(value)
    except NetworkTableError:
        raise
    except Exception:
        raise NetworkTableError("NETWORK_TABLE_SCHEMA") from None


def parse_table(raw):
    try:
        require(type(raw) is bytes and 0 < len(raw) <= 1024*1024, "NETWORK_TABLE_BOUND")
        return validate(json.loads(raw, object_pairs_hook=unique,
                                   parse_constant=lambda _: require(False, "NETWORK_TABLE_SCHEMA")))
    except NetworkTableError:
        raise
    except Exception:
        raise NetworkTableError("NETWORK_TABLE_SCHEMA") from None


def render_table(value):
    """Protected consumers only: this contains topology, not a public report."""
    return encoded(validate(value))


def new_table(image, table_id):
    image = validate_image(image)
    return validate(dict(schema_version=1, kind="NETWORK_TABLE", visibility="PROTECTED_LOCAL",
                         table_id=table_id, installation_id=image["installation_id"],
                         domain_id=image["domain_id"], revision=1, catalogue=image,
                         descriptions={}, addressing={}))


def draft(value, device_id):
    value = validate(value)
    require(any(e is not None and e["device_id"] == device_id for e in value["catalogue"]["entries"]),
            "NETWORK_DEVICE_UNKNOWN")
    current = value["descriptions"].get(device_id)
    body = copy.deepcopy(current["description"]) if current else dict(
        device_kind="UNKNOWN", platform=dict(os="UNKNOWN", architecture="UNKNOWN"),
        roles=[], launch_mode={}, transports=[], capabilities={k: "UNKNOWN" for k in CAPABILITIES},
        stable_ip="UNKNOWN")
    return proposal(dict(schema_version=1, expected_revision=value["revision"], device_id=device_id,
                         description=body))


def fact_status(row, entry, *, now, clock_trusted=True):
    if row is None or row["source"] == "NONE":
        return dict(value="UNKNOWN", source="NONE", freshness="UNKNOWN")
    freshness = ("CLOCK_UNCERTAIN" if not clock_trusted or row["observed_at"] > now else
                 "STALE" if now-row["observed_at"] >= row["valid_for_s"]
                 or row["endpoint_digest"] != endpoint_digest(entry) else "FRESH")
    return dict(value=row["value"] if freshness == "FRESH" else "UNKNOWN",
                source=row["source"], freshness=freshness)


def notices(image, value, *, now, clock_trusted=True):
    """Safe finite status; observation hints/addresses never enter assistance output."""
    image = validate_image(image)
    require(integer(now) and type(clock_trusted) is bool, "NETWORK_CLOCK")
    if value is not None:
        value = validate(value, installation=image["installation_id"], domain=image["domain_id"])
    result = []
    for entry in image["entries"]:
        if entry is None:
            continue
        device_id = entry["device_id"]
        row = None if value is None else value["descriptions"].get(device_id)
        missing = [] if row is None else missing_fields(row["description"])
        state = ("MISSING_DESCRIPTION" if row is None else
                 "CLOCK_UNCERTAIN" if not clock_trusted or now < row["approved_at"] else
                 "STALE_DESCRIPTION" if now-row["approved_at"] >= row["valid_for_s"] else
                 "INADEQUATE_DESCRIPTION" if missing else "DESCRIBED")
        result.append(dict(device_id=device_id, alias=entry["alias"], description_status=state,
                           missing=missing, stable_ip=fact_status(
                               None if value is None else value["addressing"].get(device_id), entry,
                               now=now, clock_trusted=clock_trusted)))
    return dict(schema_version=1, kind="NETWORK_DESCRIPTION_STATUS", devices=result,
                needs_description=sum(e["description_status"] != "DESCRIBED" for e in result),
                table_revision=None if value is None else value["revision"])


def addressing_prerequisite(value, device_id, *, required, now):
    """One prerequisite only; READY here is never authorization to execute."""
    value = validate(value)
    require(type(required) is bool and integer(now), "NETWORK_ACTION_PREREQUISITE")
    entry = next((e for e in value["catalogue"]["entries"]
                  if e is not None and e["device_id"] == device_id), None)
    require(entry is not None, "NETWORK_DEVICE_UNKNOWN")
    if not required:
        return "NOT_REQUIRED"
    fact = fact_status(value["addressing"].get(device_id), entry, now=now)
    return ("SATISFIED" if fact == dict(value="ASSIGNED", source="FIXED_HELPER", freshness="FRESH")
            else "STABLE_ADDRESS_REQUIRED")


@dataclass(frozen=True, repr=False)
class AddressingObservation:
    """Trusted read-only adapter fact, not a JSON/self-asserted capability."""
    device_id: str
    endpoint_digest: str
    value: str
    observed_at: int
    valid_for_s: int

