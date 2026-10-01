"""Unreleased R2 exact native-document IO. Not wired into installed v1.

The injected Docs service must have locally authorized credentials and bounded
HTTP timeouts. This module never loads credentials, creates/discovers a document,
or executes a payload. File ACLs are not application role authorization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from uuid import UUID

from tb4.exchange_layout import MAX_DOCUMENT_BYTES, encoded, slots, validate_document, LayoutError
from tb4.security_contract import parse_control, PolicyError


class AuthorityError(ValueError):
    """Only stable public codes; never retain provider messages or document data."""


def require(condition, code):
    if not condition:
        raise AuthorityError(code)


def units(text):
    try:
        return len(text.encode("utf-16-le")) // 2
    except (AttributeError, UnicodeError):
        raise AuthorityError("TEXT_ENCODING") from None


@dataclass(frozen=True, repr=False)
class AuthorityBinding:
    document_id: str
    tab_id: str
    domain_id: str

    def __post_init__(self):
        for value in (self.document_id, self.tab_id):
            require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,256}", value), "OBJECT_BINDING")
        try:
            require(str(UUID(self.domain_id)) == self.domain_id, "DOMAIN_BINDING")
        except (ValueError, AttributeError, TypeError):
            raise AuthorityError("DOMAIN_BINDING") from None


def document_bytes(value):
    # Docs strips BMP private-use characters on insert. Escape only that range
    # in JSON so decoded data and hashes survive without changing other Unicode.
    text = encoded(value).decode("utf-8")
    return re.sub("[\ue000-\uf8ff]", lambda m: "\\u%04x" % ord(m[0]), text).encode("utf-8")


def validated(raw, binding):
    try:
        value = parse_control(raw)
        capacity = validate_document(value)
        require(value["domain_id"] == binding.domain_id, "DOMAIN_BINDING")
        require(document_bytes(value) == raw, "NONCANONICAL_CONTROL")
        require(len(raw) <= capacity.worst_case_bytes, "WIRE_CAPACITY")
        require(all(len(document_bytes({k:v})) <= slots(capacity)[k]
                    for k,v in value["records"].items()), "WIRE_SLOT_BUDGET")
        return value
    except (PolicyError, LayoutError):
        raise AuthorityError("CONTROL_INVALID") from None


@dataclass(frozen=True, repr=False)
class Snapshot:
    binding: AuthorityBinding
    revision: str
    raw: bytes
    end_index: int
    _origin: object = field(compare=False)

    def document(self):
        # Fresh object each time: caller edits cannot alter the observed read.
        return validated(self.raw, self.binding)


class WriteResult(StrEnum):
    ACCEPTED = "ACCEPTED"  # Still requires readback.
    REJECTED = "REJECTED"  # A 400/409/412 is not assumed to mean revision conflict.
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


def _status(error):
    value = getattr(getattr(error, "resp", None), "status", None)
    return value if type(value) is int else None


class NativeDocsAuthority:
    """One fixed single-tab machine document; strict CAS, no raw-file fallback."""

    def __init__(self, service, binding: AuthorityBinding):
        require(isinstance(binding, AuthorityBinding), "OBJECT_BINDING")
        self._service, self.binding, self._origin = service, binding, object()

    def read(self):
        try:
            response = self._service.documents().get(
                documentId=self.binding.document_id, includeTabsContent=True,
                suggestionsViewMode="SUGGESTIONS_INLINE").execute(num_retries=0)
        except Exception:
            raise AuthorityError("READ_UNAVAILABLE") from None
        return self._decode(response)

    def _decode(self, response):
        # Bounds apply before walking rich structures. The HTTP layer must also
        # bound response bytes/time before deserialization (later runtime wiring).
        try:
            require(len(encoded(response)) <= 4 * MAX_DOCUMENT_BYTES, "WIRE_SIZE")
            require(type(response) is dict and response.get("documentId") == self.binding.document_id,
                    "OBJECT_BINDING")
            revision = response.get("revisionId")
            require(type(revision) is str and 1 <= len(revision) <= 1024, "REVISION_MISSING")
            tabs = response.get("tabs")
            require(type(tabs) is list and len(tabs) == 1, "TAB_SHAPE")
            tab = tabs[0]
            require(tab["tabProperties"]["tabId"] == self.binding.tab_id
                    and not tab.get("childTabs"), "TAB_BINDING")
            document = tab["documentTab"]
            require(not any(document.get(k) for k in ("headers", "footers", "footnotes",
                    "inlineObjects", "positionedObjects")), "RICH_CONTENT")
            content = document["body"]["content"]
            require(type(content) is list and len(content) == 2, "BODY_SHAPE")
            section, paragraph = content
            require(set(section) <= {"startIndex", "endIndex", "sectionBreak"}
                    and section.get("startIndex", 0) == 0 and section["endIndex"] == 1
                    and "sectionBreak" in section, "BODY_SHAPE")
            require(set(paragraph) == {"startIndex", "endIndex", "paragraph"}
                    and paragraph["startIndex"] == 1, "BODY_SHAPE")
            para = paragraph["paragraph"]
            require(set(para) <= {"elements", "paragraphStyle"}, "RICH_CONTENT")
            chunks, position = [], 1
            elements = para["elements"]
            require(type(elements) is list and 1 <= len(elements) <= 4096, "TEXT_SHAPE")
            for element in elements:
                require(set(element) == {"startIndex", "endIndex", "textRun"}, "RICH_CONTENT")
                run = element["textRun"]
                require(set(run) <= {"content", "textStyle"}, "RICH_CONTENT")
                text = run["content"]
                require(type(text) is str and element["startIndex"] == position, "TEXT_RANGE")
                position += units(text)
                require(element["endIndex"] == position, "TEXT_RANGE")
                chunks.append(text)
            text = "".join(chunks)
            require(paragraph["endIndex"] == position and text.endswith("\n")
                    and "\n" not in text[:-1], "TERMINAL_NEWLINE")
            raw = text[:-1].encode("utf-8")
            validated(raw, self.binding)
            return Snapshot(self.binding, revision, raw, position, self._origin)
        except (KeyError, TypeError, AttributeError, UnicodeError, LayoutError):
            raise AuthorityError("WIRE_INVALID") from None

    def compare_replace(self, observed, desired):
        require(isinstance(observed, Snapshot) and observed._origin is self._origin
                and observed.binding == self.binding, "SNAPSHOT_ORIGIN")
        old = observed.document()
        raw = document_bytes(desired)
        validated(raw, self.binding)
        # Capacity/layout migration is a separate authorized commissioning path.
        require(all(old[k] == desired[k] for k in old if k != "records"), "LAYOUT_CHANGED")
        require(observed.end_index == units(observed.raw.decode("utf-8")) + 2, "TEXT_RANGE")
        body = {"writeControl": {"requiredRevisionId": observed.revision}, "requests": [
            {"deleteContentRange": {"range": {"tabId": self.binding.tab_id,
                "startIndex": 1, "endIndex": observed.end_index - 1}}},
            {"insertText": {"location": {"tabId": self.binding.tab_id, "index": 1},
                "text": raw.decode("utf-8")}},
        ]}
        try:
            response = self._service.documents().batchUpdate(
                documentId=self.binding.document_id, body=body).execute(num_retries=0)
        except Exception as error:
            status = _status(error)
            if status in {400, 409, 412}:
                return WriteResult.REJECTED
            if status in {401, 403, 404}:
                return WriteResult.UNAVAILABLE
            return WriteResult.UNKNOWN  # Includes 429, 5xx, lost response.
        # A missing/malformed receipt cannot authorize subsequent work.
        if type(response) is not dict or response.get("documentId") != self.binding.document_id:
            return WriteResult.UNKNOWN
        return WriteResult.ACCEPTED
