"""Closed shared same-folder intent; no private path or physical permission."""
from dataclasses import asdict
import copy

from .configuration_contract import require
from .drive.commissioning import SetupSpec,digest
from .drive.folder_authority import FolderBinding
from .exchange_layout import Capacity
from .drive.leadership import transition_id as hex64
from .reconfiguration_root_plan import stable_records


def folder_plan(value):
    require(type(value) is dict and set(value)=={"schema_version","mode","transition_id",
        "operation_id","authority","blueprint_sha256","handle_sha256","mapping_sha256","records_sha256"}
        and type(value["schema_version"]) is int and value["schema_version"]==1
        and value["mode"]=="FOLDER_SQLITE_V1" and type(value["authority"]) is dict
        and set(value["authority"])=={"root_id","domain_id"}
        and all(hex64(value[k]) for k in ("transition_id","operation_id","blueprint_sha256",
            "handle_sha256","mapping_sha256","records_sha256")),"FOLDER_RELOCATION_PLAN")
    FolderBinding(**value["authority"])
    require(value["operation_id"]==digest(["folder-relocation",value["transition_id"],value["mapping_sha256"]]),
            "FOLDER_RELOCATION_PLAN")
    return copy.deepcopy(value)


def matches_folder_plan(document,binding,value):
    folder_plan(value)
    require(type(binding) is FolderBinding,"FOLDER_RELOCATION_PLAN")
    row=document["records"]["global.commissioning"];marker=row["body"]
    spec=SetupSpec(marker["root_id"],binding.domain_id,marker["setup_id"],marker["bootstrap_actor"],
                   marker["mode"],Capacity.parse(document["capacity"]))
    return (value["authority"]==asdict(binding) and spec.mode=="FOLDER_SQLITE_V1"
        and marker==spec.marker("STORAGE_READY") and row["retention"]=="RETAINED"
        and row["generation"]==0 and row["operation_id"]==spec.setup_id
        and value["blueprint_sha256"]==spec.fingerprint
        and value["records_sha256"]==stable_records(document))
