"""Immutable protected authority evidence; no public payload or auto-recovery.

Use a fresh native PrivateSettings store per evidence image. Revision one avoids
duplicating a near-budget authority into the previous-payload frame. Creation
and retention/index management belong to the staged controller, not this helper.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import dataclass
import hashlib
import re
from uuid import UUID

from .configuration_contract import ConfigurationError, require
from .exchange_layout import MAX_DOCUMENT_BYTES, encoded
from .private_settings import PrivateSettings
from .reconfiguration_inspection import Blocker, Inspection, authority_image
from .drive.docs_authority import AuthorityBinding, validated
from .drive.folder_authority import FolderBinding

MAX_FACT_BYTES = 128 * 1024  # All fixed-layout blockers still fit a first private frame.


@dataclass(frozen=True, repr=False)
class EvidenceReceipt:
    installation_id: str
    transition_id: str
    payload_sha256: str


class ProtectedEvidence:
    def __init__(self, store, *, installation_id, transition_id):
        require(type(store) is PrivateSettings and type(installation_id) is str
                and type(transition_id) is str and re.fullmatch(r"[0-9a-f]{64}", transition_id),
                "CONFIGURATION_EVIDENCE_BINDING")
        try:
            require(str(UUID(installation_id)) == installation_id, "CONFIGURATION_EVIDENCE_BINDING")
        except (ValueError, AttributeError, TypeError):
            raise ConfigurationError("CONFIGURATION_EVIDENCE_BINDING") from None
        self.store, self.installation_id, self.transition_id = store, installation_id, transition_id

    def __repr__(self):
        return "<ProtectedEvidence>"

    def _receipt(self, payload):
        return EvidenceReceipt(self.installation_id, self.transition_id,
                               hashlib.sha256(encoded(payload)).hexdigest())

    def _validate(self, payload):
        require(type(payload) is dict and set(payload) == {
            "schema_version", "kind", "installation_id", "transition_id", "image", "inspection"}
            and type(payload["schema_version"]) is int and payload["schema_version"] == 1
            and payload["kind"] == "RECONFIGURATION_AUTHORITY_EVIDENCE"
            and payload["installation_id"] == self.installation_id
            and payload["transition_id"] == self.transition_id, "CONFIGURATION_EVIDENCE_CHANGED")
        facts = payload["inspection"]
        require(type(facts) is dict and set(facts) == {
            "authority", "revision", "raw_sha256", "setup_sha256", "blockers"}
            and len(encoded(facts)) <= MAX_FACT_BYTES, "CONFIGURATION_EVIDENCE_CHANGED")
        authority = facts["authority"]
        require(type(authority) is dict and set(authority) == {"mode", "binding"}
                and authority["mode"] in {"NATIVE_DOCS", "FOLDER_SQLITE_V1"},
                "CONFIGURATION_EVIDENCE_CHANGED")
        binding = (AuthorityBinding if authority["mode"] == "NATIVE_DOCS" else FolderBinding)(
            **authority["binding"])
        require(type(facts["revision"]) is str and 1 <= len(facts["revision"]) <= 1024
                if authority["mode"] == "NATIVE_DOCS" else
                type(facts["revision"]) is int and 1 <= facts["revision"] <= 2**63 - 1,
                "CONFIGURATION_EVIDENCE_CHANGED")
        require(type(payload["image"]) is str
                and len(payload["image"]) <= (MAX_DOCUMENT_BYTES + 2) // 3 * 4,
                "CONFIGURATION_EVIDENCE_SIZE")
        raw = base64.b64decode(payload["image"], validate=True)
        require(base64.b64encode(raw).decode("ascii") == payload["image"]
                and type(facts["raw_sha256"]) is str
                and facts["raw_sha256"] == hashlib.sha256(raw).hexdigest()
                and type(facts["setup_sha256"]) is str
                and re.fullmatch(r"[0-9a-f]{64}", facts["setup_sha256"]),
                "CONFIGURATION_EVIDENCE_CHANGED")
        validated(raw, binding)
        require(type(facts["blockers"]) is list, "CONFIGURATION_EVIDENCE_CHANGED")
        for row in facts["blockers"]:
            require(type(row) is dict and set(row) == {"kind", "identity"},
                    "CONFIGURATION_EVIDENCE_CHANGED")
            Blocker(**row)

    def preserve(self, snapshot, inspection, *, owner_authorized=False):
        require(owner_authorized is True, "CONFIGURATION_OWNER_REQUIRED")
        authority, _ = authority_image(snapshot)
        require(type(inspection) is Inspection and inspection.authority == authority
                and inspection.revision == snapshot.revision
                and inspection.raw_sha256 == hashlib.sha256(snapshot.raw).hexdigest(),
                "CONFIGURATION_EVIDENCE_CHANGED")
        facts = inspection.private_record()
        require(len(encoded(facts)) <= MAX_FACT_BYTES and len(snapshot.raw) <= MAX_DOCUMENT_BYTES,
                "CONFIGURATION_EVIDENCE_SIZE")
        payload = dict(schema_version=1, kind="RECONFIGURATION_AUTHORITY_EVIDENCE",
                       installation_id=self.installation_id, transition_id=self.transition_id,
                       image=base64.b64encode(snapshot.raw).decode("ascii"), inspection=facts)
        try:
            self._validate(payload)
            old = self.store.read()
            if old is None:
                old = self.store.save(payload, expected_revision=0)
            require(old.revision == 1 and old.previous is None and old.payload == payload,
                    "CONFIGURATION_EVIDENCE_IMMUTABLE")
            require(self.store.read() == old, "CONFIGURATION_EVIDENCE_UNCONFIRMED")
            return self._receipt(payload)
        except ConfigurationError:
            raise
        except Exception:
            # Pending/failed readback must be inspected, never overwritten here.
            raise ConfigurationError("CONFIGURATION_EVIDENCE_UNCONFIRMED") from None

    def read(self, receipt):
        require(type(receipt) is EvidenceReceipt and receipt.installation_id == self.installation_id
                and receipt.transition_id == self.transition_id, "CONFIGURATION_EVIDENCE_BINDING")
        try:
            current = self.store.read()
            require(current is not None and current.revision == 1 and current.previous is None
                    and current.payload.get("installation_id") == self.installation_id
                    and current.payload.get("transition_id") == self.transition_id
                    and self._receipt(current.payload) == receipt, "CONFIGURATION_EVIDENCE_CHANGED")
            self._validate(current.payload)
            return copy.deepcopy(current.payload)  # Protected caller only, never a UI projection.
        except ConfigurationError:
            raise
        except Exception:
            raise ConfigurationError("CONFIGURATION_EVIDENCE_UNCONFIRMED") from None
