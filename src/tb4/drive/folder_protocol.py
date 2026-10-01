"""Closed, bounded one-request protocol for the optional folder authority.

The helper configuration and command are private commissioning data. RPC contains
no path, shell command, credential, provisioning, discovery or delete operation.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import json
import re
import secrets

from tb4.exchange_layout import MAX_DOCUMENT_BYTES, MAX_GENERATION, encoded
from .docs_authority import AuthorityError, WriteResult, document_bytes, require, validated
from .folder_authority import FolderBinding

MAX_WIRE = 2 * MAX_DOCUMENT_BYTES
MODE = "FOLDER_SQLITE_V1"


def flat_json(raw):
    require(type(raw) is bytes and 2 <= len(raw) <= MAX_WIRE, "RPC_SIZE")
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, "RPC_DUPLICATE")
            out[key] = value
        return out
    try:
        # Bound nesting before the standard decoder allocates recursive objects.
        depth, quoted, escape = 0, False, False
        for char in raw:
            if quoted:
                if escape: escape = False
                elif char == 92: escape = True
                elif char == 34: quoted = False
            elif char == 34: quoted = True
            elif char in (123, 91):
                depth += 1
                require(depth <= 2, "RPC_DEPTH")
            elif char in (125, 93): depth -= 1
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        require(type(value) is dict and len(value) <= 10
                and all(type(v) in {str, int, type(None)} for v in value.values()), "RPC_SHAPE")
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise AuthorityError("RPC_INVALID") from None


def header(binding, nonce):
    return dict(version=1, mode=MODE, root=binding.root_id, domain=binding.domain_id, nonce=nonce)


def check_header(value, binding, nonce=None):
    require(type(value.get("version")) is int and value["version"] == 1
            and value.get("mode") == MODE and value.get("root") == binding.root_id
            and value.get("domain") == binding.domain_id, "RPC_BINDING")
    require(type(value.get("nonce")) is str and re.fullmatch("[a-f0-9]{32}", value["nonce"])
            and (nonce is None or value["nonce"] == nonce), "RPC_NONCE")


def body_bytes(value, binding):
    try:
        require(type(value) is str and len(value) <= (MAX_DOCUMENT_BYTES + 2) // 3 * 4, "RPC_BODY")
        raw = base64.b64decode(value, validate=True)
        require(base64.b64encode(raw).decode("ascii") == value, "RPC_BODY")
        validated(raw, binding)
        return raw
    except (ValueError, UnicodeError):
        raise AuthorityError("RPC_BODY") from None


def handle(store, raw):
    """Exactly one request. No retries; an uncorrelated error is not a receipt."""
    reply = None
    try:
        request = flat_json(raw)
        check_header(request, store.binding)
        reply = header(store.binding, request["nonce"])
        operation = request.get("operation")
        require(operation in {"READ", "CAS"} and set(request) == set(reply) | {"operation"}
                | ({"expected", "body"} if operation == "CAS" else set()), "RPC_FIELDS")
        if operation == "READ":
            revision, body = store.read()
            reply.update(result="SNAPSHOT", revision=revision, body=base64.b64encode(body).decode("ascii"))
        else:
            body = body_bytes(request["body"], store.binding)
            require(type(request["expected"]) is int and 1 <= request["expected"] < MAX_GENERATION,
                    "REVISION_INVALID")
            reply.update(result=str(store.compare_replace(request["expected"], body)))
    except Exception:
        # Even a local failure after a commit is ambiguous. Never claim rollback.
        reply = {**(reply or {}), "result": "UNKNOWN"}
    return encoded(reply)


@dataclass(frozen=True, repr=False)
class FolderAccess:
    """Trusted setup attestation, not accepted from shared data or LLM arguments.

    Installation must verify BOTH the role's helper and an authorized LLM adapter
    reach this binding. A Drive-only connector does not attest folder access.
    """
    binding: FolderBinding
    llm_authorized: bool
    role_authorized: bool


@dataclass(frozen=True, repr=False)
class FolderSnapshot:
    binding: FolderBinding
    revision: int
    raw: bytes
    _origin: object = field(compare=False)

    def document(self): return validated(self.raw, self.binding)


class FolderAuthority:
    def __init__(self, transport, binding, access):
        require(type(binding) is FolderBinding and type(access) is FolderAccess
                and access.binding == binding and access.llm_authorized is True
                and access.role_authorized is True, "SAME_EXCHANGE_ACCESS_REQUIRED")
        require(getattr(transport, "binding", None) == binding and callable(getattr(transport, "call", None)),
                "HELPER_BINDING")
        self.transport, self.binding, self._origin = transport, binding, object()

    def _call(self, operation, **fields):
        nonce = secrets.token_hex(16)
        request = {**header(self.binding, nonce), "operation": operation, **fields}
        require(getattr(self.transport, "binding", None) == self.binding, "HELPER_BINDING")
        try:
            response = flat_json(self.transport.call(encoded(request)))
        except Exception:
            raise AuthorityError("HELPER_UNAVAILABLE") from None
        check_header(response, self.binding, nonce)
        return response

    def read(self):
        response = self._call("READ")
        require(set(response) == set(header(self.binding, "")) | {"result", "revision", "body"}
                and response["result"] == "SNAPSHOT", "READ_UNAVAILABLE")
        revision = response["revision"]
        require(type(revision) is int and 1 <= revision <= MAX_GENERATION, "REVISION_INVALID")
        return FolderSnapshot(self.binding, revision, body_bytes(response["body"], self.binding), self._origin)

    def compare_replace(self, observed, desired):
        require(type(observed) is FolderSnapshot and observed._origin is self._origin
                and observed.binding == self.binding, "SNAPSHOT_ORIGIN")
        old, raw = observed.document(), document_bytes(desired)
        validated(raw, self.binding)
        require(all(old[k] == desired[k] for k in old if k != "records"), "LAYOUT_CHANGED")
        try:
            response = self._call("CAS", expected=observed.revision, body=base64.b64encode(raw).decode("ascii"))
            require(set(response) == set(header(self.binding, "")) | {"result"}, "RPC_FIELDS")
            return WriteResult(response["result"])
        except Exception:
            return WriteResult.UNKNOWN

