"""Closed shared destination/fixed-reference witness; facts never grant routing."""
import copy
import re

from .configuration_contract import require
from .drive.commissioning import SetupSpec,digest,object_id
from .drive.docs_authority import AuthorityBinding
from .exchange_layout import Capacity


def root_plan(value):
    require(type(value) is dict and set(value) == {"schema_version","mode","transition_id",
        "source_root","target_root","blueprint_sha256","references_sha256","records_sha256"}
        and type(value["schema_version"]) is int and value["schema_version"] == 1
        and value["mode"] == "NATIVE_DOCS" and object_id(value["source_root"])
        and object_id(value["target_root"]) and value["source_root"] != value["target_root"]
        and all(type(value[k]) is str and re.fullmatch("[a-f0-9]{64}",value[k]) for k in (
            "transition_id","blueprint_sha256","references_sha256","records_sha256")),
        "CONFIGURATION_ROOT_PLAN")
    return copy.deepcopy(value)


def stable_records(document):
    return digest({k:v for k,v in document["records"].items()
                   if k not in {"global.leadership","global.force_request","global.summary"}})


def references(document,binding):
    require(type(binding) is AuthorityBinding and document["domain_id"] == binding.domain_id,
            "CONFIGURATION_ROOT_BINDING")
    row = document["records"]["global.commissioning"]; marker = row["body"]
    try:
        spec = SetupSpec(marker["root_id"],binding.domain_id,marker["setup_id"],marker["bootstrap_actor"],
                         marker["mode"],Capacity.parse(document["capacity"]))
        from .commissioning_records import current_record
        current_record(document,spec,root_transition=marker.get("reconfiguration",{}).get("transition_id"))
        require(spec.mode == "NATIVE_DOCS", "CONFIGURATION_ROOT_BLUEPRINT")
        result = []
        for key in spec.artifact_keys:
            _,index,kind = key.split(".")
            item = document["records"]["target."+index+".catalogue"]["body"]["artifacts"][kind]
            require(object_id(item["id"]) and item["seal"] == digest([
                spec.mode,spec.root_id,spec.domain_id,item["id"],spec.operation(key)]),
                "CONFIGURATION_ROOT_BINDING")
            result.append(dict(key=key,id=item["id"],seal=item["seal"]))
        result.append(dict(key="authority",id=binding.document_id,seal=digest([
            spec.mode,spec.root_id,spec.domain_id,binding.document_id,binding.tab_id])))
        require(len({item["id"] for item in result}) == len(result), "CONFIGURATION_ROOT_BINDING")
        return spec,result
    except Exception:
        from .configuration_contract import ConfigurationError
        raise ConfigurationError("CONFIGURATION_ROOT_BINDING") from None


def matches_plan(document,binding,plan):
    root_plan(plan)
    spec,refs = references(document,binding)
    return (plan["source_root"] == spec.root_id and plan["blueprint_sha256"] == spec.fingerprint
            and plan["references_sha256"] == digest(refs)
            and plan["records_sha256"] == stable_records(document))
