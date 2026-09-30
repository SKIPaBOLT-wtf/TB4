"""R2 commissioning contracts; pure validation/projection, no device or Drive IO.

The caller supplies protected data from authorized commissioning. These models
do not authorize deployment, prove backend fencing or grant a credential.
"""
from __future__ import annotations

import copy
import ipaddress
from uuid import UUID as ParsedUUID

from jsonschema import Draft202012Validator, FormatChecker

from tb4.privacy import closed

UUID = {"type": "string", "format": "uuid"}
ALIAS = {"type": "string", "pattern": "^[a-z][a-z0-9-]{0,31}$"}
TEXT = {"type": "string", "minLength": 1, "maxLength": 128}
ROLES = {"type": "array", "items": {"enum": ["watchdog", "fetcher"]}, "minItems": 1, "maxItems": 2, "uniqueItems": True}
PLATFORM = closed({"os": {"enum": ["WINDOWS", "LINUX", "OTHER", "UNKNOWN"]},
                   "architecture": {"enum": ["X64", "ARM64", "X86", "OTHER", "UNKNOWN"]}})
LAUNCH = {"type": "object", "propertyNames": {"enum": ["watchdog", "fetcher"]},
          "additionalProperties": {"enum": ["DESKTOP_SESSION", "OS_SERVICE", "EXTERNAL", "UNSUPPORTED"]}}
CAPABILITIES = ("ssh_status", "ssh_start", "wake", "fetcher_execution")
FACTS = {
    "network": ["ONLINE", "OFFLINE", "UNKNOWN"],
    "ssh_transport": ["REACHABLE", "UNREACHABLE", "UNKNOWN"],
    "ssh_auth": ["AUTHORIZED", "DENIED", "UNKNOWN"],
    "installation": ["PRESENT", "ABSENT", "UNKNOWN"],
    "fetcher_liveness": ["ALIVE", "STOPPED", "UNKNOWN"],
    "acceptance": ["READY", "NOT_READY", "UNKNOWN"],
    "result": ["DONE", "FAILED", "UNKNOWN"],
}
SOURCES = ["OWNER_DECLARATION", "LOCAL_INSPECTION", "NETWORK_PROBE", "FIXED_HELPER", "RUNTIME_HEARTBEAT", "CORRELATED_RESULT", "NONE"]


def observation(values):
    return closed({"value": {"enum": values}, "source": {"enum": SOURCES},
                   "observed_at": {"type": ["integer", "null"], "minimum": 0, "maximum": 10**12},
                   "valid_for_s": {"type": ["integer", "null"], "minimum": 1, "maximum": 31_536_000}})


CAPABILITY_SCHEMA = {"type": "object", "propertyNames": {"enum": list(CAPABILITIES)},
                     "additionalProperties": observation(["SUPPORTED", "UNSUPPORTED", "UNQUALIFIED", "UNKNOWN"])}
FACT_SCHEMA = {"type": "object", "properties": {k: observation(v) for k, v in FACTS.items()}, "additionalProperties": False}
TRANSPORTS = {"type": "array", "maxItems": 4, "uniqueItems": True,
              "items": {"enum": ["DRIVE_API", "SHARED_FOLDER", "SSH", "WOL"]}}
INTERFACE = closed({"name": TEXT, "segment": ALIAS, "kind": {"enum": ["LAN", "VPN", "WAN", "ISOLATED"]},
                    "addresses": {"type": "array", "maxItems": 32, "uniqueItems": True,
                                  "items": {"type": "string", "maxLength": 64}}})
DEVICE_PROPERTIES = {"device_id": UUID, "alias": ALIAS, "roles": ROLES, "platform": PLATFORM,
                     "launch_mode": LAUNCH, "transports": TRANSPORTS,
                     "capabilities": CAPABILITY_SCHEMA, "observations": FACT_SCHEMA}
LOCAL_DEVICE = closed({**DEVICE_PROPERTIES, "display_name": TEXT,
                       "interfaces": {"type": "array", "maxItems": 32, "items": INTERFACE}})
SHARED_DEVICE = closed(DEVICE_PROPERTIES)
LOCAL_SCHEMA = closed({
    "schema_version": {"const": 1}, "kind": {"const": "BALLPARK_LOCAL"},
    "visibility": {"const": "PROTECTED_LOCAL"}, "installation_id": UUID, "domain_id": UUID,
    "revision": {"type": "integer", "minimum": 1},
    "topology": {"enum": ["FLAT", "ROUTED", "MULTI_SUBNET", "VPN", "ISOLATED", "MIXED"]},
    "devices": {"type": "array", "minItems": 1, "maxItems": 256, "items": LOCAL_DEVICE},
})
SHARED_SCHEMA = closed({
    "schema_version": {"const": 1}, "kind": {"const": "BALLPARK_CATALOGUE"},
    "visibility": {"const": "PRIVATE_SHARED"}, "domain_id": UUID,
    "revision": {"type": "integer", "minimum": 1},
    "devices": {"type": "array", "minItems": 1, "maxItems": 256, "items": SHARED_DEVICE},
})


def summary_fact(values):
    return closed({"value": {"enum": values}, "freshness": {"enum": ["FRESH", "STALE", "UNKNOWN", "CLOCK_UNCERTAIN"]}})


SUMMARY_SCHEMA = closed({
    "schema_version": {"const": 1}, "kind": {"const": "BALLPARK_SUMMARY"},
    "visibility": {"const": "PRIVATE_LLM"}, "domain_id": UUID,
    "revision": {"type": "integer", "minimum": 1},
    "devices": {"type": "array", "minItems": 1, "maxItems": 256, "items": closed({
        **{k: v for k, v in DEVICE_PROPERTIES.items() if k not in {"capabilities", "observations"}},
        "capabilities": closed({name: summary_fact(["SUPPORTED", "UNSUPPORTED", "UNQUALIFIED", "UNKNOWN"]) for name in CAPABILITIES}),
        "observations": closed({name: summary_fact(values) for name, values in FACTS.items()}),
    })},
})
SCHEMA_BUNDLE = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                 "$defs": {"local": LOCAL_SCHEMA, "shared": SHARED_SCHEMA, "summary": SUMMARY_SCHEMA},
                 "oneOf": [{"$ref": "#/$defs/" + name} for name in ("local", "shared", "summary")]}


class BallparkError(ValueError):
    """Fixed code only; validation never embeds protected input in errors."""


def require(condition, code):
    if not condition:
        raise BallparkError(code)


def shape(value, schema):
    require(not next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), None),
            "BALLPARK_SCHEMA_INVALID")


def validate(value, *, shared=False):
    shape(value, SHARED_SCHEMA if shared else LOCAL_SCHEMA)
    for name in (("domain_id",) if shared else ("domain_id", "installation_id")):
        require(str(ParsedUUID(value[name])) == value[name], "BALLPARK_IDENTITY_NONCANONICAL")
    identities, aliases = set(), set()
    addresses = {}
    for device in value["devices"]:
        identity, alias = device["device_id"], device["alias"]
        require(alias == alias.strip(), "BALLPARK_ALIAS_INVALID")
        require(str(ParsedUUID(identity)) == identity, "BALLPARK_IDENTITY_NONCANONICAL")
        require(identity not in identities and alias not in aliases, "BALLPARK_IDENTITY_COLLISION")
        identities.add(identity)
        aliases.add(alias)
        require(set(device["launch_mode"]) == set(device["roles"]), "BALLPARK_LAUNCH_ROLE_MISMATCH")
        for fact in [*device["capabilities"].values(), *device["observations"].values()]:
            known = fact["value"] != "UNKNOWN"
            require(not known or (fact["source"] != "NONE" and fact["observed_at"] is not None
                                  and fact["valid_for_s"] is not None), "BALLPARK_OBSERVATION_UNPROVEN")
            require((fact["observed_at"] is None) == (fact["valid_for_s"] is None), "BALLPARK_FRESHNESS_INCOMPLETE")
        # Availability observations need actual observations, not setup declarations.
        for name, fact in device["observations"].items():
            if fact["value"] == "UNKNOWN":
                continue
            allowed = {
                "network": {"NETWORK_PROBE"}, "ssh_transport": {"FIXED_HELPER"},
                "ssh_auth": {"FIXED_HELPER"}, "installation": {"LOCAL_INSPECTION", "FIXED_HELPER"},
                "fetcher_liveness": {"RUNTIME_HEARTBEAT"}, "acceptance": {"RUNTIME_HEARTBEAT"},
                "result": {"CORRELATED_RESULT"},
            }
            require(fact["source"] in allowed[name], "BALLPARK_OBSERVATION_SOURCE_INVALID")
        if shared:
            continue
        names = set()
        for interface in device["interfaces"]:
            require(interface["name"] not in names, "BALLPARK_INTERFACE_COLLISION")
            names.add(interface["name"])
            for address in interface["addresses"]:
                try:
                    parsed = ipaddress.ip_interface(address)
                except ValueError:
                    raise BallparkError("BALLPARK_ADDRESS_INVALID") from None
                require("/" in address and "%" not in address, "BALLPARK_ADDRESS_INVALID")
                key = (interface["segment"], str(parsed.ip))
                require(key not in addresses, "BALLPARK_ADDRESS_COLLISION")
                addresses[key] = identity
    return copy.deepcopy(value)


def catalogue(local):
    local = validate(local)
    shared = dict(schema_version=1, kind="BALLPARK_CATALOGUE", visibility="PRIVATE_SHARED",
                  domain_id=local["domain_id"], revision=local["revision"], devices=[
                      {k: copy.deepcopy(d[k]) for k in DEVICE_PROPERTIES} for d in local["devices"]])
    return validate(shared, shared=True)


def effective(observation_value, now):
    if not observation_value or observation_value["value"] == "UNKNOWN":
        return {"value": "UNKNOWN", "freshness": "UNKNOWN"}
    age = now - observation_value["observed_at"]
    if age < 0:
        return {"value": "UNKNOWN", "freshness": "CLOCK_UNCERTAIN"}
    if age >= observation_value["valid_for_s"]:
        return {"value": "UNKNOWN", "freshness": "STALE"}
    return {"value": observation_value["value"], "freshness": "FRESH"}


def llm_projection(shared, *, now):
    shared = validate(shared, shared=True)
    require(type(now) is int and 0 <= now <= 10**12, "BALLPARK_CLOCK_INVALID")
    result = dict(schema_version=1, kind="BALLPARK_SUMMARY", visibility="PRIVATE_LLM",
                domain_id=shared["domain_id"], revision=shared["revision"], devices=[{
                    "device_id": d["device_id"], "alias": d["alias"], "roles": list(d["roles"]),
                    "platform": copy.deepcopy(d["platform"]), "launch_mode": dict(d["launch_mode"]),
                    "transports": list(d["transports"]),
                    "capabilities": {name: effective(d["capabilities"].get(name), now) for name in CAPABILITIES},
                    "observations": {name: effective(d["observations"].get(name), now) for name in FACTS},
                } for d in shared["devices"]])
    shape(result, SUMMARY_SCHEMA)
    return result


def validate_revision(previous, candidate, *, expected_revision):
    previous, candidate = validate(previous), validate(candidate)
    require(type(expected_revision) is int and previous["revision"] == expected_revision
            and candidate["revision"] == expected_revision + 1, "BALLPARK_REVISION_CONFLICT")
    require(previous["domain_id"] == candidate["domain_id"]
            and previous["installation_id"] == candidate["installation_id"], "BALLPARK_DOMAIN_CHANGED")
    before = {d["device_id"] for d in previous["devices"]}
    after = {d["device_id"] for d in candidate["devices"]}
    require(before <= after, "BALLPARK_REMOVAL_REQUIRES_MAINTENANCE")
    return candidate


def publication_candidate(previous, proposal, *, actor, installation_id, owner_authorized):
    """Pure policy gate, not authenticated storage publication.

    Authorization parameters must come from local commissioned control state,
    never proposal/device text. RP-008/026/029 supply fencing and active authority.
    """
    schema = closed({"instruction_source": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
                     "expected_revision": {"type": "integer", "minimum": 1}, "candidate": LOCAL_SCHEMA})
    shape(proposal, schema)
    require(actor == "WATCHDOG" and owner_authorized is True, "BALLPARK_AUTHORITY_REQUIRED")
    require(installation_id == previous.get("installation_id"), "BALLPARK_INSTALLATION_MISMATCH")
    return catalogue(validate_revision(previous, proposal["candidate"], expected_revision=proposal["expected_revision"]))
