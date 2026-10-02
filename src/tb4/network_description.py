"""Deterministic description assistance from one verified repository workflow."""
import hashlib
import json

from .instructions import RuntimeFacts, check_boundary, select
from .network_table import (GUIDANCE, SCHEMA_BUNDLE, draft, missing_fields, parse_proposal,
                            render_proposal, require)
from .network_table_store import LocalNetworkTable

SCHEMA = "protocol/network-description-v1.schema.json"


class DescriptionAssistant:
    def __init__(self, table, *, source, runtime):
        require(type(table) is LocalNetworkTable and type(runtime) is RuntimeFacts, "NETWORK_GUIDANCE_CONTEXT")
        self.table, self.source, self.runtime = table, source, runtime
        self.pin = None
        self._candidate = None

    def begin(self, device_id):
        self.pin = select(self.source, self.runtime)
        self.pin.read(GUIDANCE)
        try:
            require(json.loads(self.pin.read(SCHEMA)) == SCHEMA_BUNDLE, "NETWORK_GUIDANCE_SCHEMA")
        except Exception:
            self.pin = None
            require(False, "NETWORK_GUIDANCE_SCHEMA")
        self._candidate = None
        return draft(self.table.read(), device_id)

    def propose(self, raw):
        require(self.pin is not None, "NETWORK_GUIDANCE_REQUIRED")
        check_boundary(self.source, self.pin, self.runtime)
        value = parse_proposal(raw)
        current = draft(self.table.read(), value["device_id"])
        require(current["expected_revision"] == value["expected_revision"], "NETWORK_REVISION_CHANGED")
        self._candidate = render_proposal(value)
        return dict(candidate_digest=hashlib.sha256(self._candidate).hexdigest(),
                    missing=missing_fields(value["description"]))

    def confirm(self, candidate_digest, *, now, owner_authorized=False):
        require(self.pin is not None and self._candidate is not None, "NETWORK_GUIDANCE_REQUIRED")
        require(owner_authorized is True and type(candidate_digest) is str
                and hashlib.sha256(self._candidate).hexdigest() == candidate_digest,
                "NETWORK_OWNER_APPROVAL_REQUIRED")
        check_boundary(self.source, self.pin, self.runtime)
        result = self.table.approve(parse_proposal(self._candidate), now=now,
                                    owner_authorized=True, instruction_commit=self.pin.commit)
        self._candidate = None
        return result
