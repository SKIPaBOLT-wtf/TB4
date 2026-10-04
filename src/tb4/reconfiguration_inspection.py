"""Pure bounded inspection of one authority image and this installation's WAL.

This is evidence, never a grant, a cross-machine ACK barrier or proof that an
external effect stopped. Unknown effects require exact-operation resolution.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import hashlib

from .commissioning_state import storage_spec, validated
from .configuration_contract import require
from .drive.docs_authority import Snapshot as DocsSnapshot
from .drive.folder_protocol import FolderSnapshot
from .exchange_layout import MAX_GENERATION, encoded, validate_document
from .watchdog.leadership_runtime import Action, Checkpoint, Receipt
from .drive.authority_transaction import RecordMutation
from .drive.leadership import ElectionMutation, Grant, transition_id

METADATA = frozenset({"global.leadership", "global.force_request", "global.commissioning",
                      "global.settings", "global.registry"})
UNRESOLVED = frozenset({"BUSY", "UNREAD", "UNKNOWN"})
PACKAGES = ("discovery", "ballpark_publication", "enrollments", "fetcher_enrollment", "network_table")
KINDS = frozenset({"SHARED_BUSY", "SHARED_UNREAD", "SHARED_UNKNOWN", "LOCAL_SETUP_UNKNOWN",
                   "LOCAL_PENDING", "LOCAL_ELECTION", "LOCAL_MUTATION", "LOCAL_EFFECT_UNKNOWN",
                   "SHARED_EFFECT_UNKNOWN", "SHARED_EVIDENCE_REQUIRED"})


def workload_fingerprint(document):
    """Private resolution binding; heartbeat progress is not a workload change."""
    validate_document(document)
    return hashlib.sha256(encoded({key: row for key, row in document["records"].items()
                                   if key not in METADATA})).hexdigest()


@dataclass(frozen=True, repr=False)
class Blocker:
    kind: str
    identity: str  # Protected evidence only; never included in public_summary.

    def __post_init__(self):
        require(type(self.kind) is str and self.kind in KINDS
                and type(self.identity) is str and 1 <= len(self.identity) <= 128,
                "CONFIGURATION_INSPECTION")


@dataclass(frozen=True, repr=False)
class Inspection:
    authority: dict
    revision: str | int
    raw_sha256: str
    setup_sha256: str
    blockers: tuple[Blocker, ...]

    def public_summary(self):
        counts = {}
        for row in self.blockers:
            counts[row.kind] = counts.get(row.kind, 0) + 1
        return dict(schema_version=1, scope="LOCAL_INSTALLATION_AND_SHARED_IMAGE",
                    requires_resolution=bool(counts), counts=dict(sorted(counts.items())),
                    execution_authorized=False)

    def private_record(self):
        return dict(authority=copy.deepcopy(self.authority), revision=self.revision,
                    raw_sha256=self.raw_sha256, setup_sha256=self.setup_sha256,
                    blockers=[asdict(row) for row in self.blockers])


def authority_image(snapshot):
    require(type(snapshot) in {DocsSnapshot, FolderSnapshot}, "CONFIGURATION_SNAPSHOT")
    if type(snapshot) is DocsSnapshot:
        require(type(snapshot.revision) is str and 1 <= len(snapshot.revision) <= 1024,
                "CONFIGURATION_SNAPSHOT")
        mode = "NATIVE_DOCS"
    else:
        require(type(snapshot.revision) is int and 1 <= snapshot.revision <= MAX_GENERATION,
                "CONFIGURATION_SNAPSHOT")
        mode = "FOLDER_SQLITE_V1"
    # Each concrete adapter validates canonical bytes, binding and fixed budgets.
    try:
        document = snapshot.document()
        return dict(mode=mode, binding=asdict(snapshot.binding)), document
    except Exception:
        from .configuration_contract import ConfigurationError
        raise ConfigurationError("CONFIGURATION_SNAPSHOT") from None


def inspect(snapshot, *, setup_payload, checkpoint):
    authority, document = authority_image(snapshot)
    try:
        payload = validated(setup_payload)
    except Exception:
        from .configuration_contract import ConfigurationError
        raise ConfigurationError("CONFIGURATION_LOCAL_SETTINGS") from None
    require(payload["choices"]["storage"] is not None, "CONFIGURATION_LOCAL_BINDING")
    spec, handle = storage_spec(payload["choices"]["storage"])
    require(spec.domain_id == snapshot.binding.domain_id and spec.mode == authority["mode"]
            and spec.capacity == validate_document(document),
            "CONFIGURATION_LOCAL_BINDING")
    if type(snapshot) is DocsSnapshot:
        require(handle.object_id == snapshot.binding.document_id and handle.tab_id == snapshot.binding.tab_id,
                "CONFIGURATION_LOCAL_BINDING")
    else:
        require(spec.root_id == snapshot.binding.root_id, "CONFIGURATION_LOCAL_BINDING")
    require(type(checkpoint) is Checkpoint and type(checkpoint.receipts) is tuple
            and len(checkpoint.receipts) <= len(Action)
            and (checkpoint.grant is None or type(checkpoint.grant) is Grant)
            and (checkpoint.election is None or type(checkpoint.election) is ElectionMutation)
            and (checkpoint.mutation is None or type(checkpoint.mutation) is RecordMutation),
            "CONFIGURATION_LOCAL_CHECKPOINT")
    require(checkpoint.maintenance is None or transition_id(checkpoint.maintenance),
            "CONFIGURATION_LOCAL_CHECKPOINT")
    if checkpoint.grant is not None:
        require(checkpoint.grant.owner == payload["installation_id"], "CONFIGURATION_LOCAL_BINDING")
    for plan in (checkpoint.election, checkpoint.mutation):
        if plan is not None:
            require(plan.binding == snapshot.binding and plan.owner.owner == payload["installation_id"],
                    "CONFIGURATION_LOCAL_BINDING")
    require(all(type(row) is Receipt and type(row.action) is Action
                and transition_id(row.operation_id) and type(row.epoch) is int
                and 1 <= row.epoch <= MAX_GENERATION
                and row.outcome in {"UNKNOWN", "COMPLETE", "NO_WORK", "SUPERSEDED", "NOT_DISPATCHED"}
                for row in checkpoint.receipts)
            and len({row.action for row in checkpoint.receipts}) == len(checkpoint.receipts),
            "CONFIGURATION_LOCAL_CHECKPOINT")
    rows = [Blocker("SHARED_" + row["retention"], key)
            for key, row in sorted(document["records"].items())
            if key not in METADATA and row["retention"] in UNRESOLVED]
    from .reconfiguration_effects import ledger, SLOT
    effects = ledger(document["records"][SLOT])
    if effects is not None:
        rows += [Blocker("SHARED_EFFECT_UNKNOWN", row["operation_id"])
                 for _,row in sorted(effects["entries"].items()) if row["outcome"] == "UNKNOWN"]
        if effects["barrier"] is not None and not effects["barrier"]["local_clear"]:
            rows.append(Blocker("SHARED_EVIDENCE_REQUIRED", effects["barrier"]["transition_id"]))
    rows += [Blocker("LOCAL_SETUP_UNKNOWN", operation)
             for operation, status in sorted(payload["operations"].items()) if status == "UNKNOWN"]
    # Only schema-validated transaction packages have a pending field. A device
    # observation/stable-IP value of UNKNOWN is not an unresolved side effect.
    for name in PACKAGES:
        value = payload.get(name)
        if type(value) is dict and value.get("pending") is not None:
            rows.append(Blocker("LOCAL_PENDING", name))
    if checkpoint.election is not None:
        rows.append(Blocker("LOCAL_ELECTION", "election"))
    if checkpoint.mutation is not None:
        rows.append(Blocker("LOCAL_MUTATION", "mutation"))
    rows += [Blocker("LOCAL_EFFECT_UNKNOWN", row.operation_id)
             for row in checkpoint.receipts if row.outcome == "UNKNOWN"]
    return Inspection(authority, snapshot.revision, hashlib.sha256(snapshot.raw).hexdigest(),
                      hashlib.sha256(encoded(payload)).hexdigest(), tuple(rows))
