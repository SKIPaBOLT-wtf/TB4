"""Typed read-only first-run adapter for the opt-in physical Folder probe.

The trusted caller supplies the commissioned fixed process. Authentication and
credential construction remain a separate boundary. This adapter has no runtime
authority, allocation, mutation or activation API.
"""
from __future__ import annotations

from tb4.commissioning_records import current_record
from tb4.commissioning_state import storage_spec
from tb4.exchange_layout import MAX_GENERATION, validate_document
from .commissioning import SetupSpec
from .commissioning_bootstrap import AuthorityHandle
from .docs_authority import AuthorityError, require, validated
from .folder_authority import FolderBinding
from .folder_probe import FolderProbe, FolderProof
from .folder_protocol import MODE
from .folder_transport import FixedProcess


class RemoteFolderCommissioning:
    def __init__(self, probe):
        require(type(probe) is FolderProbe and type(probe.spec) is SetupSpec
                and probe.spec.mode == MODE and type(probe.handle) is AuthorityHandle
                and probe.handle.object_id == probe.spec.root_id and probe.handle.tab_id is None,
                "REMOTE_STORAGE_BINDING")
        binding = FolderBinding(probe.spec.root_id, probe.spec.domain_id)
        require(probe.binding == binding and type(probe.transport) is FixedProcess
                and probe.transport.binding == binding and type(probe._origin) is object,
                "REMOTE_STORAGE_BINDING")
        self._probe, self._spec, self._handle = probe, probe.spec, probe.handle
        self._binding, self._transport, self._origin = binding, probe.transport, probe._origin

    @property
    def spec(self):
        return self._spec

    @property
    def root_id(self):
        return self._spec.root_id

    @property
    def mode(self):
        return MODE

    def verify(self, record):
        """Exactly one fresh physical observation of this protected selection."""
        try:
            spec, handle = storage_spec(record)
            probe = self._probe
            require(spec == self._spec and handle == self._handle
                    and record.get("root_transition") is None, "REMOTE_STORAGE_BINDING")
            require(type(probe) is FolderProbe and probe.spec == self._spec
                    and probe.handle == self._handle and probe.binding == self._binding
                    and probe.transport is self._transport and probe._origin is self._origin,
                    "REMOTE_STORAGE_BINDING")
            # Call the exact typed implementation, never a caller-supplied verifier.
            proof = FolderProbe.verify(probe)
            require(type(proof) is FolderProof and proof._origin is self._origin
                    and proof.spec == spec and proof.handle == handle and proof.binding == self._binding
                    and type(proof.revision) is int and 1 <= proof.revision <= MAX_GENERATION,
                    "REMOTE_STORAGE_PROOF")
            document = validated(proof.raw, self._binding)
            require(validate_document(document) == spec.capacity, "REMOTE_STORAGE_PROOF")
            current_record(document, spec)
            return document
        except Exception:
            raise AuthorityError("REMOTE_STORAGE_UNAVAILABLE") from None
