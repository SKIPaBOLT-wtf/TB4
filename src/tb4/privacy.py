"""Closed public diagnostics and deliberately separate private projections.

This is data minimization, not a sanitizer for arbitrary text or image pixels.
Unrecognized content is omitted or rejected without echoing it.
"""
from __future__ import annotations

import json
from functools import lru_cache

from jsonschema import Draft202012Validator

ROLES = frozenset({"watchdog", "fetcher"})
STATES = frozenset({"STOPPED", "STARTING", "RUNNING", "STOPPING", "EXITED", "FAILED"})
STAGES = frozenset({"STARTUP", "CONFIGURATION", "AUTHORIZATION", "ROOT_AND_MAP", "ROLE_STARTUP",
                    "ROLE_LOOP", "COOPERATIVE_STOP", "ACTION_FINISHED", "UNKNOWN"})
OUTCOMES = frozenset({"OK", "SUCCESS", "NOT_FOUND", "PERMISSION_DENIED", "CONFLICT",
                      "TRANSIENT_ERROR", "AMBIGUOUS", "EXCEPTION", "UNKNOWN"})
OBSERVATIONS = frozenset({"UNKNOWN", "RECENT_RESPONSE", "STALE", "CLOCK_UNCERTAIN"})
ERROR_CODES = frozenset({
    "UNCLASSIFIED_ERROR", "ERROR_RUNTIMEERROR", "ERROR_VALUEERROR", "ERROR_OSERROR",
    "ERROR_TIMEOUTERROR", "ERROR_PERMISSIONERROR", "ERROR_FILENOTFOUNDERROR",
    "ROLE_INVALID", "DRIVE_FOLDER_URL_INVALID", "DRIVE_ROOT_ID_REQUIRED", "PROFILE_PATH_NOT_ABSOLUTE",
    "PROFILE_SYMLINK_REFUSED", "LOCALAPPDATA_UNAVAILABLE", "LOCK_NAME_INVALID", "LOCK_SYMLINK_REFUSED",
    "PROFILE_BUSY", "CONFIG_SYMLINK_REFUSED", "CONFIG_TOO_LARGE", "CONFIG_UNREADABLE",
    "CONFIG_ROOT_MUST_BE_ID", "DEVICE_ID_REQUIRED", "CREDENTIAL_PATH_NOT_ABSOLUTE",
    "DESKTOP_SETTINGS_INVALID", "LOCAL_DRIVE_FOLDER_NOT_ABSOLUTE", "CONFIG_STRUCTURE_INVALID",
    "CONFIG_CHANGED_RELOAD_REQUIRED", "BACKUP_SYMLINK_REFUSED", "LEGACY_SERVICE_INSTALLED",
    "SERVICE_PRESENCE_UNCONFIRMED", "CONFIG_SAVE_MESSAGE_INVALID", "RETURN_RECOVERY_REQUIRES_FETCHER",
    "RETURN_RECOVERY_TICKET_INVALID", "BOOTSTRAP_REQUIRES_WATCHDOG", "OPTIONAL_LOCAL_MOUNT_UNAVAILABLE",
    "ACTION_INVALID", "RETURN_RECOVERY_CLOCK_INVALID", "RETURN_RECOVERY_ARCHIVE_INVALID",
    "RETURN_RECOVERY_READ_FAILED", "RETURN_RECOVERY_OBJECT_INVALID", "RETURN_RECOVERY_BODY_TOO_LARGE",
    "RETURN_RECOVERY_OBSERVATION_CHANGED", "RETURN_RECOVERY_BODY_INVALID", "RETURN_RECOVERY_IDENTITY_MISMATCH",
    "RETURN_RECOVERY_RESULT_INCOMPLETE", "RETURN_RECOVERY_HASH_MISMATCH", "RETURN_RECOVERY_PAYLOAD_HASH_MISMATCH",
    "RETURN_RECOVERY_STOP_REQUESTED", "RETURN_RECOVERY_PULSE_INVALID", "RETURN_RECOVERY_PULSE_FRESH",
    "RETURN_RECOVERY_STATE_INVALID", "RETURN_RECOVERY_ARCHIVE_MISMATCH", "RETURN_RECOVERY_ARCHIVE_CHANGED",
    "RETURN_RECOVERY_PUBLICATION_UNCONFIRMED",
    "ROLE_CONFIG_INVALID:VALUEERROR", "ROLE_CONFIG_INVALID:TYPEERROR", "ROLE_CONFIG_INVALID:KEYERROR",
    "AUTH_READY", "AUTH_MISSING_LOCAL_CREDENTIALS", "AUTH_INVALID_LOCAL_CREDENTIALS", "AUTH_REFRESH_FAILED",
    "AUTH_INTERACTIVE_REQUIRED", "AUTH_INTERACTIVE_FAILED", "AUTH_CLIENT_BUILD_FAILED", "AUTH_UNSUPPORTED_SCOPE",
})
SECRET_FIELDS = frozenset({"password", "token", "access_token", "refresh_token", "client_secret", "private_key", "secret_value"})
PROTECTED_FIELDS = frozenset({"topology", "host", "address", "interfaces", "port", "device_id", "domain_id",
                              "root_id", "object_id", "alias", "path", "credential_ref", "store_location",
                              "username", "payload", "environment", "provider_error", "stdout", "stderr",
                              "observed_at", "last_drive_at", "filename", "screenshot"})
PUBLIC_FIELDS = frozenset({"schema_version", "role", "process_state", "stage", "last_outcome",
                           "protocol_state", "error_code", "remote_observation", "privacy"})


class PrivacyError(ValueError):
    """Fixed diagnostic codes only."""


def classify_field(name):
    """Unknown fields default to protected; public eligibility also needs values."""
    if name in SECRET_FIELDS:
        return "LOCAL_SECRET"
    return "PUBLIC_CANDIDATE" if name in PUBLIC_FIELDS else "PROTECTED"


def allowed(value, values, fallback=None):
    return value if type(value) is str and value in values else fallback


def exception_code(error):
    # Exact built-in types only; custom exception class names are untrusted text.
    return {RuntimeError: "ERROR_RUNTIMEERROR", ValueError: "ERROR_VALUEERROR", OSError: "ERROR_OSERROR",
            TimeoutError: "ERROR_TIMEOUTERROR", PermissionError: "ERROR_PERMISSIONERROR",
            FileNotFoundError: "ERROR_FILENOTFOUNDERROR"}.get(type(error), "UNCLASSIFIED_ERROR")


@lru_cache(maxsize=1)
def canonical_protocol_names():
    from tb4.core.protocol_names import LogicalObject, state_filename
    from tb4.core.state_machine import load_state_machines
    registry = load_state_machines()
    names = set()
    for logical in LogicalObject:
        machine = registry.machine(logical)
        if machine is not None:
            for state in machine.states:
                try:
                    names.add(state_filename(logical, state))
                except ValueError:
                    pass
    return frozenset(names)


def closed(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def public_schema():
    return closed({
        "schema_version": {"const": 2}, "role": {"enum": sorted(ROLES)},
        "process_state": {"enum": sorted(STATES) + [None]}, "stage": {"enum": sorted(STAGES) + [None]},
        "last_outcome": {"enum": sorted(OUTCOMES) + [None]},
        "protocol_state": {"enum": sorted(canonical_protocol_names()) + [None]},
        "error_code": {"enum": sorted(ERROR_CODES) + [None]},
        "remote_observation": {"enum": sorted(OBSERVATIONS)},
        "privacy": {"const": "PUBLIC_ALLOWLIST_V2_REVIEW_BEFORE_UPLOAD"},
    })


def public_diagnostic(role, snapshot, observation):
    if allowed(role, ROLES) is None:
        raise PrivacyError("PUBLIC_ROLE_INVALID")
    value = snapshot if type(snapshot) is dict else {}
    return dict(schema_version=2, role=role, process_state=allowed(value.get("process_state"), STATES),
                stage=allowed(value.get("stage"), STAGES), last_outcome=allowed(value.get("last_outcome"), OUTCOMES),
                protocol_state=allowed(value.get("protocol_state"), canonical_protocol_names()),
                error_code=allowed(value.get("error_code"), ERROR_CODES),
                remote_observation=allowed(observation, OBSERVATIONS, "UNKNOWN"),
                privacy="PUBLIC_ALLOWLIST_V2_REVIEW_BEFORE_UPLOAD")


def public_artifact(kind, report):
    """Only the closed report is eligible; never copy an input export filename.

    Screenshots, binary blobs, text logs and raw config need a separate manual
    review path. This helper does not upload anything or grant review approval.
    """
    if kind != "diagnostic" or not isinstance(report, dict):
        raise PrivacyError("ARTIFACT_REQUIRES_PRIVATE_REVIEW")
    if next(Draft202012Validator(public_schema()).iter_errors(report), None):
        raise PrivacyError("PUBLIC_REPORT_INVALID")
    return f"tb4-{report['role']}-diagnostics.json", (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()


# This projection is intentionally PRIVATE. It is a narrow R2 contract seed;
# RP-005 owns complete BALLPARK topology/revision validation and publication.
PRIVATE_PROJECTION = closed({
    "schema_version": {"const": 1}, "visibility": {"const": "PRIVATE_LLM"},
    "devices": {"type": "array", "maxItems": 256, "items": closed({
        "alias": {"type": "string", "pattern": "^[a-z][a-z0-9-]{0,31}$"},
        "role": {"enum": sorted(ROLES)},
        "capabilities": closed({"ssh_status": {"type": "boolean"}, "ssh_start": {"type": "boolean"},
                                 "wake": {"type": "boolean"}}),
    })},
})


def private_projection(descriptor):
    """Explicit allowlisted projection; raw bindings/config never copied."""
    try:
        devices = descriptor["devices"]
        if type(devices) is not list or len(devices) > 256:
            raise PrivacyError("PRIVATE_PROJECTION_INVALID")
        result = {"schema_version": 1, "visibility": "PRIVATE_LLM", "devices": [
            {"alias": d["alias"], "role": d["role"], "capabilities": {
                name: d.get("capabilities", {}).get(name, False) for name in ("ssh_status", "ssh_start", "wake")}}
            for d in devices]}
        if next(Draft202012Validator(PRIVATE_PROJECTION).iter_errors(result), None):
            raise PrivacyError("PRIVATE_PROJECTION_INVALID")
        if len({d["alias"] for d in result["devices"]}) != len(result["devices"]):
            raise PrivacyError("PRIVATE_PROJECTION_INVALID")
        return result
    except (KeyError, TypeError, AttributeError):
        raise PrivacyError("PRIVATE_PROJECTION_INVALID") from None
