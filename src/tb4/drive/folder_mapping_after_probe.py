"""Fresh read-only server mapping AFTER evidence, never a runtime grant."""
from dataclasses import dataclass
from pathlib import Path

from tb4.configuration_contract import configuration
from tb4.drive.commissioning import digest
from tb4.exchange_layout import MAX_GENERATION, encoded
from tb4.private_settings import native_settings
from tb4.reconfiguration_effects import SLOT, ledger
from tb4.reconfiguration_folder_plan import folder_plan, matches_folder_plan
from tb4.watchdog.leadership_runtime import Action
from .docs_authority import AuthorityError, require, validated
from .folder_authority import FolderConfig, FolderStore
from .folder_mapping import FolderPathMapping
from .folder_probe import (FolderProbe, _check_transport, checked_document,
                          handle_probe, probe_header, check_probe_header)
from .folder_protocol import flat_json, body_bytes

MODE = "FOLDER_MAPPING_AFTER_PROBE_V1"


def after_header(binding, nonce):
    return {**probe_header(binding, nonce), "mode": MODE}


def after_request(binding, spec, authority, raw):
    value = flat_json(raw)
    require(value.get("mode") == MODE, "MAPPING_AFTER_REQUEST")
    check_probe_header({**value, "mode": probe_header(binding, "")["mode"]}, binding)
    require(set(value) == set(after_header(binding, "")) |
        {"operation", "blueprint", "authority", "mapping_sha256"}
        and value["operation"] == "VERIFY_AFTER"
        and value["blueprint"] == spec.fingerprint and value["authority"] == authority.seal
        and type(value["mapping_sha256"]) is str and len(value["mapping_sha256"]) == 64
        and all(c in "0123456789abcdef" for c in value["mapping_sha256"]), "MAPPING_AFTER_REQUEST")
    return value


def terminal_plan(document, binding, expected):
    expected = folder_plan(expected)
    summary = ledger(document["records"][SLOT])
    config = configuration(document)
    require(summary is not None and summary.get("folder_plan") == expected
        and config is not None and config["phase"] == "MAINTENANCE"
        and config["transition_id"] == expected["transition_id"]
        and matches_folder_plan(document, binding, expected), "MAPPING_AFTER_PLAN")
    entry = summary["entries"].get(Action.IDENTITY.value)
    require(entry is not None and entry["operation_id"] == expected["operation_id"]
        and entry["outcome"] == "COMPLETE", "MAPPING_AFTER_PLAN")
    return expected


def after_response(binding, spec, authority, raw, request):
    """Validate the exact private runner's correlated AFTER reply."""
    after_request(binding, spec, authority, encoded(request))
    value = flat_json(raw)
    require(value.get("mode") == MODE, "MAPPING_AFTER_RESPONSE")
    check_probe_header({**value, "mode": probe_header(binding, "")["mode"]},
                       binding, request["nonce"])
    require(set(value) == set(after_header(binding, "")) |
        {"result", "revision", "body", "mapping_sha256"}
        and value["result"] == "VERIFIED"
        and value["mapping_sha256"] == request["mapping_sha256"]
        and type(value["revision"]) is int and 1 <= value["revision"] <= MAX_GENERATION,
        "MAPPING_AFTER_RESPONSE")
    document, actual = checked_document(body_bytes(value["body"], binding), binding, spec.fingerprint)
    require(actual == spec, "MAPPING_AFTER_RESPONSE")
    summary = ledger(document["records"][SLOT])
    require(summary is not None and summary.get("folder_plan") is not None, "MAPPING_AFTER_PLAN")
    expected = terminal_plan(document, binding, summary["folder_plan"])
    require(expected["mapping_sha256"] == request["mapping_sha256"]
        and expected["blueprint_sha256"] == spec.fingerprint
        and expected["handle_sha256"] == digest(authority.record()), "MAPPING_AFTER_PLAN")
    return value


def handle_after_probe(config, raw, *, mapping_store=None):
    """Inspect the server's protected pointer; the request supplies no path."""
    reply = None
    try:
        require(type(config) is FolderConfig, "MAPPING_AFTER_CONFIG")
        value = flat_json(raw)
        require(value.get("mode") == MODE, "MAPPING_AFTER_REQUEST")
        # Discover the spec from this exact current authority, after closed fields.
        require(set(value) == set(after_header(config.binding, "")) |
            {"operation", "blueprint", "authority", "mapping_sha256"}
            and value["operation"] == "VERIFY_AFTER", "MAPPING_AFTER_REQUEST")
        check_probe_header({**value, "mode": probe_header(config.binding, "")["mode"]}, config.binding)
        from .commissioning_bootstrap import AuthorityHandle
        ordinary = {**value, "mode": probe_header(config.binding, "")["mode"], "operation": "VERIFY"}
        ordinary.pop("mapping_sha256")
        # Syntax validation precedes all protected mapping/physical IO.
        require(type(value["mapping_sha256"]) is str and len(value["mapping_sha256"]) == 64
            and all(c in "0123456789abcdef" for c in value["mapping_sha256"]), "MAPPING_AFTER_REQUEST")
        require(type(value["blueprint"]) is str and len(value["blueprint"]) == 64
            and all(c in "0123456789abcdef" for c in value["blueprint"]), "MAPPING_AFTER_REQUEST")
        require(type(value["authority"]) is str and len(value["authority"]) == 64
            and all(c in "0123456789abcdef" for c in value["authority"]), "MAPPING_AFTER_REQUEST")
        require(mapping_store is not None, "MAPPING_AFTER_UNAVAILABLE")
        mapping = FolderPathMapping(native_settings(Path(mapping_store)))
        before = mapping.read()
        require(before is not None and digest(before) == value["mapping_sha256"]
            and str(config.root) == before["target_path"], "MAPPING_AFTER_UNAVAILABLE")
        anchor = FolderConfig(Path(before["source_path"]), config.binding, config.root_identity,
                              config.db_identity, config.journal_identity)
        require(mapping.select(anchor) == config, "MAPPING_AFTER_UNAVAILABLE")
        observed = flat_json(handle_probe(config, encoded(ordinary)))
        require(observed.get("result") == "VERIFIED", "MAPPING_AFTER_UNAVAILABLE")
        document, spec = checked_document(body_bytes(observed["body"], config.binding),
                                         config.binding, value["blueprint"])
        authority = AuthorityHandle(config.binding.root_id, value["authority"], None)
        after_request(config.binding, spec, authority, raw)
        expected = terminal_plan(document, config.binding,
                                 ledger(document["records"][SLOT])["folder_plan"])
        require(expected["mapping_sha256"] == digest(before)
            and expected["transition_id"] == before["transition_id"]
            and expected["blueprint_sha256"] == spec.fingerprint
            and expected["handle_sha256"] == digest(authority.record()), "MAPPING_AFTER_PLAN")
        require(mapping.read() == before and mapping.select(anchor) == config
            and FolderStore(config).read() == (observed["revision"], body_bytes(observed["body"], config.binding)),
            "MAPPING_AFTER_CHANGED")
        reply = {**after_header(config.binding, value["nonce"]), "result": "VERIFIED",
                 "revision": observed["revision"], "body": observed["body"],
                 "mapping_sha256": digest(before)}
    except Exception:
        reply = {**(reply or {}), "result": "UNKNOWN"}
    return encoded(reply)


@dataclass(frozen=True, repr=False)
class FolderMappingAfterProof:
    binding: object
    spec: object
    handle: object
    revision: int
    raw: bytes
    plan: bytes
    _origin: object

    def document(self):
        return validated(self.raw, self.binding)


class FolderMappingAfterProbe:
    def __init__(self, probe):
        require(type(probe) is FolderProbe, "MAPPING_AFTER_CONTEXT")
        self.probe = probe
        self._pins = (probe, probe.transport, probe.spec, probe.handle, probe.binding, probe._origin)
        self._origin = object()
        self._own_origin = self._origin
        self._current()

    def _current(self):
        p = self.probe
        require(type(self) is FolderMappingAfterProbe and type(p) is FolderProbe
            and self._origin is self._own_origin and type(self._origin) is object
            and (p, p.transport, p.spec, p.handle, p.binding, p._origin) == self._pins,
            "MAPPING_AFTER_CHANGED")
        _check_transport(p.transport, p.binding, p.spec, p.handle)

    def verify(self, expected):
        try:
            self._current()
            p = self.probe
            expected = folder_plan(expected)
            require(expected["authority"] == {"root_id":p.binding.root_id, "domain_id":p.binding.domain_id}
                and expected["blueprint_sha256"] == p.spec.fingerprint
                and expected["handle_sha256"] == digest(p.handle.record()), "MAPPING_AFTER_PLAN")
            import secrets
            nonce = secrets.token_hex(16)
            request = {**after_header(p.binding, nonce), "operation":"VERIFY_AFTER",
                       "blueprint":p.spec.fingerprint, "authority":p.handle.seal,
                       "mapping_sha256":expected["mapping_sha256"]}
            after_request(p.binding, p.spec, p.handle, encoded(request))
            response = flat_json(p.transport.call(encoded(request)))
            require(response.get("mode") == MODE, "MAPPING_AFTER_RESPONSE")
            check_probe_header({**response, "mode":probe_header(p.binding, "")["mode"]}, p.binding, nonce)
            require(set(response) == set(after_header(p.binding, "")) |
                {"result", "revision", "body", "mapping_sha256"}
                and response["result"] == "VERIFIED"
                and response["mapping_sha256"] == expected["mapping_sha256"]
                and type(response["revision"]) is int
                and 1 <= response["revision"] <= MAX_GENERATION, "MAPPING_AFTER_RESPONSE")
            raw = body_bytes(response["body"], p.binding)
            document, spec = checked_document(raw, p.binding, p.spec.fingerprint)
            require(spec == p.spec, "MAPPING_AFTER_RESPONSE")
            terminal_plan(document, p.binding, expected)
            self._current()
            return FolderMappingAfterProof(p.binding, p.spec, p.handle, response["revision"],
                                           raw, encoded(expected), self._origin)
        except Exception:
            raise AuthorityError("MAPPING_AFTER_UNAVAILABLE") from None

