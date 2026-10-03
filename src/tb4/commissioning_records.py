"""Closed ready commissioning records; rebind never resets allocation/work."""
from .drive.commissioning import SetupSpec,digest
from .drive.docs_authority import require
from .exchange_layout import MAX_GENERATION


def ready_record(spec,row,*,root_transition=None,configuration_revision=None):
    require(type(spec) is SetupSpec and type(row) is dict
            and set(row)=={"generation","operation_id","retention","body"}
            and row["retention"]=="RETAINED","SETUP_MARKER")
    if row["generation"]==0:
        require(type(row["generation"]) is int and root_transition is None
                and row["operation_id"]==spec.setup_id and row["body"]==spec.marker("STORAGE_READY"),"SETUP_MARKER")
        return row
    body=row["body"];proof=body.get("reconfiguration") if type(body) is dict else None
    require(spec.mode=="NATIVE_DOCS" and type(row["generation"]) is int
            and 1<=row["generation"]<=MAX_GENERATION and type(proof) is dict
            and set(proof)=={"schema_version","transition_id","configuration_revision","previous_generation","previous_marker_sha256",
                "source_blueprint_sha256","root_plan_sha256","work_sha256","catalogues_sha256"}
            and type(proof["schema_version"]) is int and proof["schema_version"]==1
            and type(proof["previous_generation"]) is int and 0<=proof["previous_generation"]<MAX_GENERATION
            and row["generation"]==proof["previous_generation"]+1
            and type(proof["configuration_revision"]) is int and 1<=proof["configuration_revision"]<=MAX_GENERATION
            and type(configuration_revision) is int and proof["configuration_revision"]<=configuration_revision
            and all(type(proof[k]) is str and len(proof[k])==64 and all(c in "0123456789abcdef" for c in proof[k])
                    for k in ("transition_id","previous_marker_sha256","source_blueprint_sha256",
                        "root_plan_sha256","work_sha256","catalogues_sha256"))
            and root_transition==proof["transition_id"]
            and row["operation_id"]==digest(["reconfiguration-rebind",root_transition,"commissioning"])
            and body=={**spec.marker("STORAGE_READY"),"reconfiguration":proof},"SETUP_MARKER")
    return row


def current_record(document,spec,*,root_transition=None):
    from .configuration_contract import configuration
    config=configuration(document)
    return ready_record(spec,document["records"]["global.commissioning"],root_transition=root_transition,
        configuration_revision=None if config is None else config["revision"])


def rebound_record(source,target,config,*,source_blueprint_sha256,root_plan_sha256,work_sha256,catalogues_sha256):
    require(type(source["generation"]) is int and 0<=source["generation"]<MAX_GENERATION,"SETUP_MARKER")
    proof=dict(schema_version=1,transition_id=config["transition_id"],configuration_revision=config["revision"],
        previous_generation=source["generation"],previous_marker_sha256=digest(source),
        source_blueprint_sha256=source_blueprint_sha256,root_plan_sha256=root_plan_sha256,
        work_sha256=work_sha256,catalogues_sha256=catalogues_sha256)
    row=dict(generation=source["generation"]+1,
        operation_id=digest(["reconfiguration-rebind",config["transition_id"],"commissioning"]),retention="RETAINED",
        body={**target.marker("STORAGE_READY"),"reconfiguration":proof})
    return ready_record(target,row,root_transition=config["transition_id"],configuration_revision=config["revision"])
