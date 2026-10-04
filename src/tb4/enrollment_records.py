"""Closed installation binding and profile projection in existing target catalogues."""
from __future__ import annotations

import copy
import re

from .credential_contract import CredentialResolver, identity, Purpose, Outcome
from .fetcher_profile import require, integer, expand, freshness, EnrollmentError
from .exchange_layout import validate_document, encoded


def enrollment(value):
    if type(value) is str and value == "UNENROLLED":
        return None
    require(type(value) is list and len(value) == 5 and type(value[0]) is int and value[0] == 1
            and identity(value[1]) and integer(value[2], 1, 2**63-1) and integer(value[3], 0, 1)
            and type(value[4]) is str and re.fullmatch(r"[0-9a-f]{32}", value[4]), "ENROLLMENT_SCHEMA")
    return dict(installation_id=value[1], revision=value[2], state="REVOKED" if value[3] else "ENROLLED",
                nonce=value[4])


def validate_extension(body):
    binding = enrollment(body["enrollment"])
    if "fetcher" in body:
        require(binding is not None and "discovery" in body and "ballpark" in body,
                "ENROLLMENT_PROFILE_BINDING")
        expand(body["fetcher"], binding["revision"])
    elif binding is not None:
        raise EnrollmentError("ENROLLMENT_PROFILE_BINDING")
    return binding


def target(document, index):
    capacity = validate_document(document)
    require(integer(index, 0, capacity.devices-1), "ENROLLMENT_CAPACITY")
    from .ballpark_records import shared
    from .discovery_state import catalogue_record
    approved = shared(document)
    row = document["records"][f"target.{index:03d}.catalogue"]
    body = catalogue_record(row)
    discovery = body.get("discovery")
    require(discovery is not None and "ballpark" in body, "ENROLLMENT_DEVICE_NOT_APPROVED")
    matches = [d for d in approved["devices"] if d["device_id"] == discovery["device_id"]]
    require(len(matches) == 1 and matches[0]["alias"] == discovery["alias"]
            and "fetcher" in matches[0]["roles"], "ENROLLMENT_DEVICE_NOT_APPROVED")
    binding = validate_extension(body)
    profile = None if "fetcher" not in body else expand(body["fetcher"], binding["revision"])
    return row, body, matches[0], binding, profile


def binding_current(document, index, installation, revision):
    """Identity/enrollment prerequisite only; not admission or execution authority."""
    _, _, _, binding, _ = target(document, index)
    return (binding is not None and binding["state"] == "ENROLLED"
            and binding["installation_id"] == installation and binding["revision"] == revision)


def own_credentials(setup, resolver, device):
    from .commissioning_state import Setup
    require(type(setup) is Setup and setup.private_choices()["role"] == "watchdog", "ENROLLMENT_WATCHDOG")
    setup._fresh()
    require(resolver is None or type(resolver) is CredentialResolver
            and resolver._installation_id == setup.installation_id, "ENROLLMENT_CREDENTIAL_INSTALLATION")
    selected = setup.private_choices()["credentials"]
    result = {}
    # Folder commissioning is not a FETCHER bootstrap capability.
    for purpose in (Purpose.FETCHER_STATUS, Purpose.FETCHER_START):
        records = [r for r in selected if r["target_id"] == device and purpose.value in r["purposes"]]
        require(not records or resolver is not None, "ENROLLMENT_CREDENTIAL_INSTALLATION")
        values = [resolver.capability(r["handle"], purpose=purpose, target_id=device,
                                     target_trust=r["target_trust"]).report() for r in records]
        # Expose only the purpose-bound outcome, never a resolver handle/trust/path.
        ready = next((v for v in values if v["available"] and v["outcome"] == Outcome.READY.value), None)
        result[purpose.value] = ready or (values[0] if values else dict(
            configured=False, available=False, outcome=Outcome.ABSENT.value))
    return result


def view(document, setup, resolver, *, now, start=0, limit=4):
    """Bounded page of actual reports plus this WATCHDOG's own credential status."""
    require(integer(now) and integer(start, 0, 63) and integer(limit, 1, 8), "ENROLLMENT_SUMMARY_PAGE")
    from .ballpark_records import shared
    approved = shared(document)
    from .discovery_state import catalogue_record
    selected = document["records"]["global.registry"]["body"]["slots"]
    slots = []
    for index, device in zip(selected,approved["devices"]):
        if "fetcher" in device["roles"]:
            slots.append(index)
        else:
            body = catalogue_record(document["records"][f"target.{index:03d}.catalogue"])
            require(enrollment(body["enrollment"]) is None,"ENROLLMENT_DEVICE_NOT_APPROVED")
    require(start <= len(slots), "ENROLLMENT_SUMMARY_PAGE")
    targets = []
    for index in slots[start:start+limit]:
        _, _, device, binding, profile = target(document, index)
        fresh = "UNKNOWN" if profile is None else freshness(profile, now)
        state = "UNENROLLED" if binding is None else binding["state"]
        targets.append(dict(device_id=device["device_id"], alias=device["alias"], enrollment=state,
            profile=copy.deepcopy(profile), freshness=fresh,
            fetcher_liveness="ALIVE" if state == "ENROLLED" and fresh == "FRESH"
            and profile["polling"]["mode"] != "EXITED" else "UNKNOWN",
            execution_authorized=False, watchdog_credentials=own_credentials(setup, resolver, device["device_id"])))
    result = dict(kind="FETCHER_PROFILE_SUMMARY", descriptor_revision=approved["revision"],
                  targets=targets, next_start=start+limit if start+limit < len(slots) else None)
    require(len(encoded(result)) <= 8192, "ENROLLMENT_SUMMARY_CAPACITY")
    return result
