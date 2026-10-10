"""Unreleased same-authority maintenance marker; never an execution grant."""
from __future__ import annotations

import copy
import re

from .drive.docs_authority import AuthorityError
from .exchange_layout import MAX_GENERATION, validate_document
from .timing_contract import TimingProfile


class ConfigurationError(AuthorityError):
    """Closed public codes only; no private settings or authority identities."""


def require(condition, code="CONFIGURATION_INVALID"):
    if not condition:
        raise ConfigurationError(code)


def marker(value):
    require(type(value) is dict and set(value) == {
        "schema_version", "revision", "phase", "transition_id"})
    require(type(value["schema_version"]) is int and value["schema_version"] == 1
            and type(value["revision"]) is int and 1 <= value["revision"] <= MAX_GENERATION
            and type(value["phase"]) is str and value["phase"] in {"ACTIVE", "MAINTENANCE"}
            and type(value["transition_id"]) is str
            and re.fullmatch(r"[0-9a-f]{64}", value["transition_id"]) is not None)
    return copy.deepcopy(value)


def configuration(document):
    """Legacy absence is supported; an extension must be closed and coherent."""
    try:
        validate_document(document)
        row = document["records"]["global.settings"]
        body = row["body"]
        if type(body) is not dict or "configuration" not in body:
            return None
        require(set(body) == {"descriptor_state", "revision", "timing", "configuration"}
                and body["descriptor_state"] == "VALIDATED"
                and type(body["revision"]) is int and 1 <= body["revision"] <= MAX_GENERATION
                and body["revision"] == row["generation"] and row["retention"] == "RETAINED")
        TimingProfile.parse(body["timing"])
        return marker(body["configuration"])
    except ConfigurationError:
        raise
    except Exception:
        raise ConfigurationError("CONFIGURATION_INVALID") from None


def require_dispatch(document, expected_revision=None):
    """Fresh configuration admission; a local saved number alone grants nothing."""
    value = configuration(document)
    require(expected_revision is None or type(expected_revision) is int
            and 1 <= expected_revision <= MAX_GENERATION, "CONFIGURATION_REVISION_REQUIRED")
    if value is None:
        require(expected_revision is None, "CONFIGURATION_REVISION_REQUIRED")
        return
    require(value["phase"] != "MAINTENANCE", "CONFIGURATION_MAINTENANCE")
    require(expected_revision == value["revision"], "CONFIGURATION_REVISION_REQUIRED")


def dispatch_allowed(document, expected_revision=None):
    try:
        require_dispatch(document, expected_revision)
        return True
    except ConfigurationError:
        return False
