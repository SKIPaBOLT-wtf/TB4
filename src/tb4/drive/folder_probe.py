"""Opt-in read-only physical commissioning proof; never a runtime grant.

Trusted commissioning supplies a fixed authenticated transport and expected
spec/handle. Requests contain no paths, credentials, commands or allocations.
The ordinary READ/CAS helper does not accept this separate protocol.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import os
import re
import secrets

from tb4.commissioning_records import current_record
from tb4.exchange_layout import Capacity, MAX_GENERATION, encoded
from .commissioning import SetupSpec, verify_allocated_bindings
from .commissioning_bootstrap import AuthorityHandle
from .commissioning_folder import ATTR, FolderCommissioning
from .docs_authority import AuthorityError, require, validated
from .folder_authority import DB, FolderBinding, FolderConfig, FolderStore
from .folder_protocol import (MODE as AUTHORITY_MODE, FolderAccess, body_bytes,
                              check_header, flat_json, header)
from .folder_transport import FixedProcess

MODE = "FOLDER_COMMISSIONING_PROBE_V1"


def probe_header(binding, nonce):
    return {**header(binding, nonce), "mode": MODE}


def check_probe_header(value, binding, nonce=None):
    require(value.get("mode") == MODE, "PROBE_MODE")
    check_header({**value, "mode": AUTHORITY_MODE}, binding, nonce)


def checked_document(raw, binding, blueprint):
    document = validated(raw, binding)
    marker = document["records"]["global.commissioning"]["body"]
    require(type(marker) is dict, "PROBE_MARKER")
    spec = SetupSpec(binding.root_id, binding.domain_id, marker.get("setup_id"),
        marker.get("bootstrap_actor"), AUTHORITY_MODE, Capacity(**document["capacity"]))
    require(spec.fingerprint == blueprint, "PROBE_BLUEPRINT")
    current_record(document, spec)
    return document, spec


def handle_probe(config, raw):
    """One observation of the configured existing root. No send/retry/repair.

Resolve an optional protected mapping before entry. Authority inspection may
read SQLite, so finish it before taking the one physical-verification DB lock.
Artifact inspection and the final checks do not open SQLite or resolve mappings.
"""
    reply = None
    try:
        require(type(config) is FolderConfig, "PROBE_CONFIG")
        request = flat_json(raw)
        check_probe_header(request, config.binding)
        reply = probe_header(config.binding, request["nonce"])
        require(set(request) == set(reply) | {"operation", "blueprint", "authority"}
                and request["operation"] == "VERIFY", "PROBE_FIELDS")
        require(type(request["blueprint"]) is str
                and re.fullmatch("[a-f0-9]{64}", request["blueprint"]), "PROBE_BLUEPRINT")
        expected = AuthorityHandle(config.binding.root_id, request["authority"], None)
        config.verify()
        store = FolderStore(config)
        _, prior = store.read()
        _, spec = checked_document(prior, config.binding, request["blueprint"])
        port = FolderCommissioning(config.root, spec, root_identity=config.root_identity,
                                   llm_authorized=True)
        require(port.inspect_authority(spec, expected) == expected, "PROBE_AUTHORITY")
        with store.connection() as conn:
            revision, body = store._row(conn)
            document, fresh_spec = checked_document(body, config.binding, request["blueprint"])
            require(fresh_spec == spec, "PROBE_BLUEPRINT")
            require(os.getxattr(config.root / DB, ATTR) ==
                    port._marker("authority", spec.operation("authority")), "PROBE_AUTHORITY")
            verify_allocated_bindings(spec, port, document["records"], expected.object_id)
            port.check_root()
            config.verify()
        reply.update(result="VERIFIED", revision=revision,
                     body=base64.b64encode(body).decode("ascii"),
                     blueprint=spec.fingerprint, authority=expected.seal)
    except Exception:
        # Never echo provider/OS errors, private paths, or any partial proof.
        reply = {**(reply or {}), "result": "UNKNOWN"}
    return encoded(reply)


@dataclass(frozen=True, repr=False)
class FolderProof:
    binding: FolderBinding
    spec: SetupSpec
    handle: AuthorityHandle
    revision: int
    raw: bytes
    _origin: object = field(compare=False)

    def document(self):
        return validated(self.raw, self.binding)


class FolderProbe:
    """Fresh proof via the commissioned fixed command, never a saved READY flag.

This boundary does not construct SSH arguments or select credentials. Its trusted
caller must bind the exact helper, host trust and credential purpose. A proof is
an observation, not an authorization to activate, mutate, replay or adopt work.
"""
    def __init__(self, transport, spec, handle, access):
        require(type(spec) is SetupSpec and spec.mode == AUTHORITY_MODE
                and type(handle) is AuthorityHandle and handle.object_id == spec.root_id
                and handle.tab_id is None, "PROBE_BINDING")
        binding = FolderBinding(spec.root_id, spec.domain_id)
        require(type(transport) is FixedProcess and transport.binding == binding,
                "HELPER_BINDING")
        require(type(access) is FolderAccess and access.binding == binding
                and access.llm_authorized is True and access.role_authorized is True,
                "SAME_EXCHANGE_ACCESS_REQUIRED")
        self.transport, self.spec, self.handle = transport, spec, handle
        self.binding, self._origin = binding, object()

    def verify(self):
        try:
            require(type(self.transport) is FixedProcess and self.transport.binding == self.binding,
                    "HELPER_BINDING")
            nonce = secrets.token_hex(16)
            request = {**probe_header(self.binding, nonce), "operation": "VERIFY",
                       "blueprint": self.spec.fingerprint, "authority": self.handle.seal}
            response = flat_json(self.transport.call(encoded(request)))
            check_probe_header(response, self.binding, nonce)
            require(set(response) == set(probe_header(self.binding, nonce)) |
                    {"result", "revision", "body", "blueprint", "authority"}
                    and response["result"] == "VERIFIED"
                    and response["blueprint"] == self.spec.fingerprint
                    and response["authority"] == self.handle.seal, "PROBE_RESPONSE")
            revision = response["revision"]
            require(type(revision) is int and 1 <= revision <= MAX_GENERATION, "REVISION_INVALID")
            raw = body_bytes(response["body"], self.binding)
            _, spec = checked_document(raw, self.binding, self.spec.fingerprint)
            require(spec == self.spec, "PROBE_BLUEPRINT")
            return FolderProof(self.binding, spec, self.handle, revision, raw, self._origin)
        except Exception:
            raise AuthorityError("PROBE_UNAVAILABLE") from None
