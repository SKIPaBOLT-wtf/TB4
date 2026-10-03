"""Compact BALLPARK codec within the unchanged RP009 record budgets."""
from __future__ import annotations

import copy
import re

from .ballpark import catalogue, require, validate
from .ballpark_setup import GUIDANCE, digest, validate_pin
from .exchange_layout import encoded, validate_document
from .timing_contract import TimingProfile
from .configuration_contract import configuration

ROLES = ("watchdog", "fetcher")
SYSTEMS = ("WINDOWS", "LINUX", "OTHER", "UNKNOWN")
ARCH = ("X64", "ARM64", "X86", "OTHER", "UNKNOWN")
LAUNCH = ("DESKTOP_SESSION", "OS_SERVICE", "EXTERNAL", "UNSUPPORTED")
TRANSPORTS = ("DRIVE_API", "SHARED_FOLDER", "SSH", "WOL")


def code(value, choices):
    require(type(value) is int and 0 <= value < len(choices), "BALLPARK_RECORD")
    return choices[value]


def codes(value, choices, *, minimum=0):
    require(type(value) is list and minimum <= len(value) <= len(choices)
            and all(type(x) is int for x in value) and len(set(value)) == len(value), "BALLPARK_RECORD")
    return [code(x, choices) for x in value]


def compact(device, revision):
    return [1, revision, [ROLES.index(r) for r in device["roles"]],
            SYSTEMS.index(device["platform"]["os"]), ARCH.index(device["platform"]["architecture"]),
            [LAUNCH.index(device["launch_mode"][r]) for r in device["roles"]],
            [TRANSPORTS.index(t) for t in device["transports"]]]


def expand(value, discovery):
    require(type(value) is list and len(value) == 7 and type(value[0]) is int and value[0] == 1
            and type(value[1]) is int and 1 <= value[1] <= 2**63-1, "BALLPARK_RECORD")
    roles = codes(value[2], ROLES, minimum=1)
    require(type(value[5]) is list and len(value[5]) == len(roles), "BALLPARK_RECORD")
    return dict(device_id=discovery["device_id"], alias=discovery["alias"], roles=roles,
                platform=dict(os=code(value[3], SYSTEMS), architecture=code(value[4], ARCH)),
                launch_mode=dict(zip(roles, [code(x, LAUNCH) for x in value[5]])),
                transports=codes(value[6], TRANSPORTS), capabilities={}, observations={})


def provenance(draft):
    pin, decision = draft["pin"], draft["decision"]
    return dict(commit=pin["commit"], profile=pin["profile"], policy_digest=pin["policy_digest"],
                build_commit=pin["runtime"]["build_commit"], guidance_sha256=pin["files"][GUIDANCE],
                decision_id=decision["id"], decided_at=decision["at"])


def header(draft, slots):
    candidate = catalogue(draft["candidate"])
    return dict(schema_version=1, kind="BALLPARK_REVISION", codec=1, revision=candidate["revision"],
                slots=slots, sha256=digest(encoded(candidate)), provenance=provenance(draft))


def validate_header(value, capacity):
    require(type(value) is dict and set(value) == {
        "schema_version", "kind", "codec", "revision", "slots", "sha256", "provenance"}
        and type(value["schema_version"]) is int and value["schema_version"] == 1
        and value["kind"] == "BALLPARK_REVISION" and type(value["codec"]) is int and value["codec"] == 1
        and type(value["revision"]) is int and 1 <= value["revision"] <= 2**63-1,
        "BALLPARK_RECORD")
    slots = value["slots"]
    require(type(slots) is list and 1 <= len(slots) <= capacity
            and all(type(i) is int and 0 <= i < capacity for i in slots)
            and len(set(slots)) == len(slots), "BALLPARK_RECORD")
    p = value["provenance"]
    require(type(p) is dict and set(p) == {"commit", "profile", "policy_digest", "build_commit",
            "guidance_sha256", "decision_id", "decided_at"}, "BALLPARK_RECORD")
    for name, pattern in (("commit", r"[0-9a-f]{40}"), ("build_commit", r"[0-9a-f]{40}"),
                          ("profile", r"[a-z][a-z0-9-]{0,63}"), ("policy_digest", r"[0-9a-f]{64}"),
                          ("guidance_sha256", r"[0-9a-f]{64}"), ("decision_id", r"[0-9a-f]{64}")):
        require(type(p[name]) is str and re.fullmatch(pattern, p[name]), "BALLPARK_RECORD")
    require(type(p["decided_at"]) is int and 0 <= p["decided_at"] <= 10**12
            and type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]),
            "BALLPARK_RECORD")
    return value


def shared(document):
    """Decode one coherent snapshot; never assemble separately read revisions."""
    capacity = validate_document(document)
    records = document["records"]
    row, settings = records["global.registry"], records["global.settings"]
    require(row["retention"] == settings["retention"] == "RETAINED", "BALLPARK_RECORD")
    meta = validate_header(row["body"], capacity.devices)
    require(row["generation"] == meta["revision"]
            and row["operation_id"] == settings["operation_id"] == meta["provenance"]["decision_id"]
            and settings["generation"] == meta["revision"], "BALLPARK_RECORD")
    configuration(document)
    require(type(settings["body"]) is dict and set(settings["body"]) in (
            {"descriptor_state", "revision", "timing"},
            {"descriptor_state", "revision", "timing", "configuration"})
            and settings["body"]["descriptor_state"] == "VALIDATED"
            and type(settings["body"]["revision"]) is int
            and settings["body"]["revision"] == meta["revision"], "BALLPARK_RECORD")
    TimingProfile.parse(settings["body"]["timing"])
    devices = []
    from .discovery_state import catalogue_record
    for index in meta["slots"]:
        body = catalogue_record(records[f"target.{index:03d}.catalogue"])
        require("discovery" in body and "ballpark" in body and body["ballpark"][1] == meta["revision"],
                "BALLPARK_RECORD")
        devices.append(expand(body["ballpark"], body["discovery"]))
    result = dict(schema_version=1, kind="BALLPARK_CATALOGUE", visibility="PRIVATE_SHARED",
                  domain_id=document["domain_id"], revision=meta["revision"], devices=devices)
    validate(result, shared=True)
    require(digest(encoded(result)) == meta["sha256"], "BALLPARK_RECORD_DIGEST")
    return result


def receipt(draft, timing):
    return dict(pin=copy.deepcopy(draft["pin"]), decision=copy.deepcopy(draft["decision"]),
                shared_sha256=digest(encoded(catalogue(draft["candidate"]))), timing=copy.deepcopy(timing))


def validate_receipt(value, choices):
    require(type(value) is dict and set(value) in (
            {"pin", "decision", "shared_sha256", "timing"},
            {"pin", "decision", "shared_sha256", "timing", "adoption"}),
            "BALLPARK_RECEIPT")
    validate_pin(value["pin"])
    local = validate(choices["descriptor"])
    decision = value["decision"]
    require(type(decision) is dict and set(decision) == {"id", "at", "kind", "candidate_digest"}
            and type(decision["id"]) is str and re.fullmatch(r"[0-9a-f]{64}", decision["id"])
            and type(decision["at"]) is int and 0 <= decision["at"] <= 10**12
            and decision["kind"] == "LOCAL_OWNER_CONFIRMATION"
            and decision["candidate_digest"] == digest(encoded(local))
            and value["shared_sha256"] == digest(encoded(catalogue(local)))
            and value["timing"] == choices["timing"], "BALLPARK_RECEIPT")
    if "adoption" in value:
        validate_adoption(value["adoption"], choices)
    return value


def validate_adoption(value, choices):
    """Closed private provenance of a local adoption, never a shared write grant."""
    from .commissioning_state import storage_spec
    from .configuration_contract import marker
    from .drive.docs_authority import AuthorityBinding
    from dataclasses import asdict
    require(type(value) is dict and set(value) == {
        "schema_version", "kind", "configuration", "authority", "provenance"}
        and type(value["schema_version"]) is int and value["schema_version"] == 1
        and value["kind"] == "CURRENT_ACTIVE_ADOPTION", "BALLPARK_ADOPTION")
    require(marker(value["configuration"])["phase"] == "ACTIVE", "BALLPARK_ADOPTION")
    spec, handle = storage_spec(choices["storage"])
    require(spec.mode == "NATIVE_DOCS" and value["authority"] == dict(mode="NATIVE_DOCS",
        binding=asdict(AuthorityBinding(handle.object_id, handle.tab_id, spec.domain_id))), "BALLPARK_ADOPTION")
    # The original shared decision is not presented as this local confirmation.
    local = catalogue(choices["descriptor"])
    validate_header(dict(schema_version=1, kind="BALLPARK_REVISION", codec=1,
        revision=local["revision"], slots=list(range(len(local["devices"]))),
        sha256=digest(encoded(local)), provenance=value["provenance"]), spec.capacity.devices)
    return value
