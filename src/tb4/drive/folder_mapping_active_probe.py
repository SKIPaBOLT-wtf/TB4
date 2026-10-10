"""Fresh physical mapping proof after retained ACTIVE publication.

This separate mode preserves the MAINTENANCE-only AFTER contract. The client
must still match its frozen publication; an observation is never a grant.
"""
from dataclasses import asdict
from pathlib import Path
import secrets

from tb4.configuration_contract import configuration
from tb4.drive.commissioning import digest
from tb4.exchange_layout import MAX_GENERATION, encoded
from tb4.private_settings import native_settings
from tb4.reconfiguration_effects import SLOT, ledger, covered
from tb4.reconfiguration_folder_plan import folder_plan
from tb4.watchdog.leadership_runtime import Action
from .commissioning_bootstrap import AuthorityHandle
from .docs_authority import AuthorityError, require
from .folder_authority import FolderConfig, FolderStore
from .folder_mapping import FolderPathMapping
from .folder_mapping_after_probe import FolderMappingAfterProbe, FolderMappingAfterProof
from .folder_probe import checked_document, handle_probe, probe_header, check_probe_header
from .folder_protocol import flat_json, body_bytes

MODE = "FOLDER_MAPPING_ACTIVE_PROBE_V1"


def active_header(binding, nonce):
    return {**probe_header(binding, nonce), "mode": MODE}


def _request(binding, raw):
    value = flat_json(raw)
    require(value.get("mode") == MODE, "MAPPING_ACTIVE_REQUEST")
    check_probe_header({**value, "mode": probe_header(binding, "")["mode"]}, binding)
    require(set(value) == set(active_header(binding, "")) |
        {"operation", "blueprint", "authority", "mapping_sha256"}
        and value["operation"] == "VERIFY_ACTIVE", "MAPPING_ACTIVE_REQUEST")
    require(all(type(value[k]) is str and len(value[k]) == 64
        and all(c in "0123456789abcdef" for c in value[k])
        for k in ("blueprint", "authority", "mapping_sha256")), "MAPPING_ACTIVE_REQUEST")
    return value


def active_request(binding, spec, authority, raw):
    value = _request(binding, raw)
    require(value["blueprint"] == spec.fingerprint and value["authority"] == authority.seal,
            "MAPPING_ACTIVE_REQUEST")
    return value


def active_mapping(document, mapping_sha256):
    summary = ledger(document["records"][SLOT])
    config = configuration(document)
    require(config is not None and config["phase"] == "ACTIVE" and summary is not None
        and "folder_plan" not in summary and "root_plan" not in summary
        and covered(document, config["transition_id"]), "MAPPING_ACTIVE_PLAN")
    entry = summary["entries"].get(Action.IDENTITY.value)
    require(entry is not None and entry["outcome"] == "COMPLETE"
        and entry["operation_id"] == digest([
            "folder-relocation", config["transition_id"], mapping_sha256]), "MAPPING_ACTIVE_PLAN")
    return config


def active_response(binding, spec, authority, raw, request):
    active_request(binding, spec, authority, encoded(request))
    value = flat_json(raw)
    require(value.get("mode") == MODE, "MAPPING_ACTIVE_RESPONSE")
    check_probe_header({**value, "mode": probe_header(binding, "")["mode"]},
                       binding, request["nonce"])
    require(set(value) == set(active_header(binding, "")) |
        {"result", "revision", "body", "mapping_sha256"}
        and value["result"] == "VERIFIED"
        and value["mapping_sha256"] == request["mapping_sha256"]
        and type(value["revision"]) is int and 1 <= value["revision"] <= MAX_GENERATION,
        "MAPPING_ACTIVE_RESPONSE")
    document, actual = checked_document(body_bytes(value["body"], binding), binding, spec.fingerprint)
    require(actual == spec, "MAPPING_ACTIVE_RESPONSE")
    active_mapping(document, request["mapping_sha256"])
    return value


def handle_active_probe(config, raw, *, mapping_store=None):
    try:
        require(type(config) is FolderConfig, "MAPPING_ACTIVE_CONFIG")
        value = _request(config.binding, raw)  # Closed syntax before protected mapping IO.
        require(mapping_store is not None, "MAPPING_ACTIVE_UNAVAILABLE")
        mapping = FolderPathMapping(native_settings(Path(mapping_store)))
        before = mapping.read()
        require(before is not None and digest(before) == value["mapping_sha256"]
            and str(config.root) == before["target_path"], "MAPPING_ACTIVE_UNAVAILABLE")
        anchor = FolderConfig(Path(before["source_path"]), config.binding, config.root_identity,
                              config.db_identity, config.journal_identity)
        require(mapping.select(anchor) == config, "MAPPING_ACTIVE_UNAVAILABLE")
        ordinary = {**probe_header(config.binding, value["nonce"]), "operation": "VERIFY",
                    "blueprint": value["blueprint"], "authority": value["authority"]}
        observed = flat_json(handle_probe(config, encoded(ordinary)))
        require(observed.get("result") == "VERIFIED", "MAPPING_ACTIVE_UNAVAILABLE")
        document, spec = checked_document(body_bytes(observed["body"], config.binding),
                                         config.binding, value["blueprint"])
        authority = AuthorityHandle(config.binding.root_id, value["authority"], None)
        active_request(config.binding, spec, authority, raw)
        current = active_mapping(document, digest(before))
        require(current["transition_id"] == before["transition_id"]
            and current["revision"] == before["configuration_revision"] + 1
            and before["blueprint_sha256"] == spec.fingerprint
            and before["handle_sha256"] == digest(authority.record()), "MAPPING_ACTIVE_PLAN")
        require(mapping.read() == before and mapping.select(anchor) == config
            and FolderStore(config).read() == (observed["revision"], body_bytes(observed["body"], config.binding)),
            "MAPPING_ACTIVE_CHANGED")
        return encoded({**active_header(config.binding, value["nonce"]), "result": "VERIFIED",
                        "revision": observed["revision"], "body": observed["body"],
                        "mapping_sha256": digest(before)})
    except Exception:
        return encoded({"result": "UNKNOWN"})


class FolderMappingActiveProbe:
    def __init__(self, probe):
        self._after = FolderMappingAfterProbe(probe)
        self._pin = self._after
        self._origin = object()
        self._own_origin = self._origin

    def _current(self):
        require(type(self) is FolderMappingActiveProbe and self._after is self._pin
            and type(self._after) is FolderMappingAfterProbe
            and self._origin is self._own_origin, "MAPPING_ACTIVE_CHANGED")
        self._after._current()

    def verify(self, expected):
        try:
            self._current()
            p = self._after.probe
            expected = folder_plan(expected)
            require(expected["authority"] == asdict(p.binding)
                and expected["blueprint_sha256"] == p.spec.fingerprint
                and expected["handle_sha256"] == digest(p.handle.record()), "MAPPING_ACTIVE_PLAN")
            request = {**active_header(p.binding, secrets.token_hex(16)), "operation": "VERIFY_ACTIVE",
                       "blueprint": p.spec.fingerprint, "authority": p.handle.seal,
                       "mapping_sha256": expected["mapping_sha256"]}
            active_request(p.binding, p.spec, p.handle, encoded(request))
            response = active_response(p.binding, p.spec, p.handle,
                                       p.transport.call(encoded(request)), request)
            raw = body_bytes(response["body"], p.binding)
            document, _ = checked_document(raw, p.binding, p.spec.fingerprint)
            require(active_mapping(document, expected["mapping_sha256"])["transition_id"]
                == expected["transition_id"], "MAPPING_ACTIVE_PLAN")
            self._current()
            return FolderMappingAfterProof(p.binding, p.spec, p.handle, response["revision"],
                                           raw, encoded(expected), self._origin)
        except Exception:
            raise AuthorityError("MAPPING_ACTIVE_UNAVAILABLE") from None

