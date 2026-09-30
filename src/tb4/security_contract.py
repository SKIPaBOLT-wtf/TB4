"""Unreleased RP-012 policy specification. No authentication or runtime IO.

Facts and proof sets below model already verified trusted inputs. An arbitrary
caller cannot turn these predicates into a credential, execution grant or release.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

from tb4.command_contract import ContractError, validate_shape
from tb4.exchange_layout import MAX_DOCUMENT_BYTES, encoded


class PolicyError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise PolicyError(code)


BASE = {"principal_enrolled", "scope_matches", "compatible_instructions"}
WRITE = {"authority_fresh", "conditional_revision", "binding_matches"}
LEADER = {"current_owner", "no_pending_takeover"}
WORK = {"payload_verified", "deadline_valid", "local_identity_unique", "durable_execution_identity"}
RULES = {
    "read_summary": ({"LLM", "COACH_HELPER", "WATCHDOG", "STANDBY"}, set()),
    "read_result": ({"LLM", "COACH_HELPER"}, {"binding_matches", "result_verified"}),
    "submit_ingress": ({"COACH_HELPER"}, WRITE | {"user_authorized", "payload_verified", "capacity_reserved"}),
    "cancel_request": ({"COACH_HELPER"}, WRITE | {"user_authorized"}),
    "consume_result": ({"COACH_HELPER"}, WRITE | {"result_verified", "explicit_consumption"}),
    "request_takeover": ({"GUI_HELPER"}, WRITE | {"user_authorized"}),
    "claim_stale_owner": ({"STANDBY"}, WRITE | {"staleness_proven", "local_identity_unique"}),
    "claim_requested_owner": ({"STANDBY"}, WRITE | {"request_matches_candidate", "local_identity_unique"}),
    "renew_owner": ({"WATCHDOG"}, WRITE | LEADER),
    "route_work": ({"WATCHDOG"}, WRITE | LEADER | {"payload_verified", "capacity_reserved"}),
    "network_observe": ({"WATCHDOG"}, {"authority_fresh", "scope_matches"} | LEADER),
    "fixed_launch": ({"WATCHDOG"}, {"authority_fresh", "host_identity_verified", "launcher_commissioned"} | LEADER),
    "manage_network": ({"WATCHDOG"}, {"authority_fresh", "user_authorized", "network_capability_qualified", "typed_broker_only"} | LEADER),
    "recycle_consumed": ({"WATCHDOG"}, WRITE | LEADER | {"result_verified", "explicit_consumption"}),
    "read_own_work": ({"FETCHER"}, {"authority_fresh", "binding_matches"}),
    "claim_own_work": ({"FETCHER"}, WRITE | WORK),
    "publish_result": ({"FETCHER"}, WRITE | {"durable_result", "result_verified"}),
    "publish_heartbeat": ({"FETCHER"}, WRITE | {"local_identity_unique"}),
    "execute_payload": ({"RUNNER"}, {"binding_matches", "user_authorized", "least_privileged"} | WORK),
    "terminate_owned_process": ({"RUNNER"}, {"binding_matches", "owned_process_identity", "termination_authorized"}),
    "prepare_artifact": ({"LOCAL_HELPER"}, {"binding_matches", "payload_verified", "capacity_reserved", "private_temp_verified"}),
    "resolve_credential": ({"CREDENTIAL_RESOLVER"}, {"purpose_authorized", "local_identity_unique", "local_store_verified"}),
    "reset_deployment": ({"SETUP_HELPER"}, WRITE | {"user_authorized", "quiescence_proven", "reset_scope_verified"}),
}
ACTORS = set().union(*(actors for actors, _ in RULES.values()))
FACTS = BASE | set().union(*(facts for _, facts in RULES.values()))


def action_policy(actor, action, facts):
    """Pure predicate classification, never a bearer authorization capability."""
    require(type(actor) is str and actor in ACTORS, "ACTOR")
    require(type(action) is str and action in RULES, "ACTION")
    require(type(facts) is dict and set(facts) == FACTS
            and all(type(value) is bool for value in facts.values()), "FACTS")
    actors, needed = RULES[action]
    missing = sorted((BASE | needed) - {key for key,value in facts.items() if value})
    return dict(decision="MODEL_PREDICATES_SATISFIED" if actor in actors and not missing else "DENY",
                missing=missing, actor_allowed=actor in actors, runtime_authorization=False)


# All rows preserve work/evidence. Failure handling never grants replay permission.
FAULTS = {
    "COMMAND_NONZERO": ("OPERATION", "PUBLISH_EXECUTION_EVIDENCE"),
    "PARTIAL_EFFECTS": ("OPERATION", "PRESERVE_AND_REVIEW_EFFECTS"),
    "CANCEL_REQUESTED": ("OPERATION", "WAIT_FOR_ACTUAL_EXECUTION_EVIDENCE"),
    "UNKNOWN_EXECUTION": ("OPERATION", "RECONCILE_SAME_EXECUTION"),
    "STALE_RESULT": ("OPERATION", "REJECT_STALE_GENERATION"),
    "MALFORMED_INGRESS": ("OPERATION", "CORRELATED_REJECTION"),
    "OUTPUT_LIMIT": ("OPERATION", "PRESERVE_CAPTURE_COMPLETENESS"),
    "HOST_OFFLINE": ("TARGET", "WAIT_FOR_COMMISSIONED_ROUTE"),
    "SSH_UNAVAILABLE": ("TARGET", "KEEP_VALID_POLLING_ROUTE"),
    "SSH_IDENTITY_CHANGED": ("TARGET", "BLOCK_TARGET_LAUNCH"),
    "CREDENTIAL_UNAVAILABLE": ("TARGET", "BLOCK_REQUIRED_CAPABILITY"),
    "AUTHORITY_CREDENTIAL_UNAVAILABLE": ("TRANSPORT", "RETAIN_LOCAL_OUTBOX_STOP_SHARED_MUTATION"),
    "RUNNER_PERMISSION": ("TARGET", "REPORT_NO_IMPLICIT_ELEVATION"),
    "WRITE_REPLY_LOST": ("TRANSPORT", "INSPECT_SAME_TRANSITION"),
    "PROVIDER_UNAVAILABLE": ("TRANSPORT", "RETAIN_LOCAL_OUTBOX_STOP_SHARED_MUTATION"),
    "RATE_LIMIT": ("TRANSPORT", "BOUNDED_RECONCILIATION_WITH_CONTROL_RESERVE"),
    "CLOCK_UNQUALIFIED": ("CAPABILITY", "BLOCK_UNQUALIFIED_TIME_DECISION"),
    "OWNER_SUPERSEDED": ("COORDINATOR", "DEMOTE_BEFORE_NEW_DISPATCH"),
    "AUTHORITY_IDENTITY_AMBIGUOUS": ("DOMAIN", "BLOCK_MUTATION_NO_REPLACEMENT_ROOT"),
    "AUTHORITY_BODY_CORRUPT": ("DOMAIN", "PRESERVE_INVALID_AUTHORITY"),
    "AUTHORITY_ACCESS_COMPROMISED": ("DOMAIN", "STOP_MUTATION_REQUIRE_ACCESS_REVIEW"),
}


def failure_policy(code):
    require(type(code) is str and code in FAULTS, "FAULT_CODE")
    scope, action = FAULTS[code]
    return dict(scope=scope, action=action, preserve_evidence=True,
                automatic_replay=False, automatic_clear=False,
                waits_for_all_sink_ack=False)


GATES = {
    "authority_cas": ["RP-015", "RP-016"],
    "cooperative_role_enforcement": ["RP-017", "RP-018", "RP-031", "RP-043"],
    "private_principal_acl": ["RP-022", "RP-024", "RP-059"],
    "protected_credentials_windows": ["RP-020"],
    "protected_credentials_linux": ["RP-021"],
    "native_windows_identity": ["RP-018", "RP-044", "RP-055"],
    "native_linux_identity": ["RP-018", "RP-045", "RP-056"],
    "durable_unknown_and_output": ["RP-039", "RP-046", "RP-047", "RP-048", "RP-049", "RP-050"],
    "bounded_parser_media_rate": ["RP-031", "RP-049", "RP-058", "RP-059"],
    "instruction_result_boundary": ["RP-051", "RP-052", "RP-059"],
    "same_host_roles": ["RP-060", "RP-062"],
    "separate_hosts": ["RP-060", "RP-063"],
    "windows_fixed_launch": ["RP-036", "RP-042", "RP-060"],
    "linux_fixed_launch": ["RP-037", "RP-042", "RP-060"],
    "no_launcher_idle": ["RP-038", "RP-041", "RP-042", "RP-060"],
    "wake_topology": ["RP-038", "RP-060", "RP-063"],
    "network_change_capability": ["RP-026", "RP-060", "RP-063"],
    "headless_session": ["RP-020", "RP-021", "RP-030", "RP-036", "RP-037", "RP-060"],
    "package_release_and_live_authority": ["RP-055", "RP-056", "RP-057", "RP-059", "RP-061", "RP-062", "RP-063", "RP-064"],
}
COMMON_GATES = {"authority_cas", "cooperative_role_enforcement", "private_principal_acl",
    "durable_unknown_and_output", "bounded_parser_media_rate", "instruction_result_boundary",
    "package_release_and_live_authority"}
DIMENSIONS = {
    "backend": {"NATIVE_DOCS", "RAW_DRIVE_V1", "SYNCED_FILES", "MEMORY_TEST"},
    "platform": {"WINDOWS", "LINUX", "OTHER"},
    "topology": {"SAME_HOST", "SEPARATE_HOSTS"},
    "launcher": {"NONE", "SSH_FIXED", "OS_FIXED", "EXTERNAL_FIXED"},
    "session": {"DESKTOP", "SERVICE", "HEADLESS"},
    "editor_trust": {"AUTHORIZED_COOPERATIVE", "UNTRUSTED_EDITOR"},
    "workload_trust": {"OWNER_AUTHORIZED", "HOSTILE_SANDBOX_REQUIRED"},
    "wake": {"NONE", "COMMISSIONED"},
    "network_change": {"NONE", "SCOPED_AUTHORIZED"},
}


def mode_policy(selection, satisfied_gates=frozenset()):
    """Requirements inventory only; does not validate real evidence or release."""
    require(type(selection) is dict and set(selection) == set(DIMENSIONS), "MODE_SHAPE")
    require(all(type(value) is str and value in DIMENSIONS[key] for key,value in selection.items()), "MODE_VALUE")
    require(type(satisfied_gates) in {set,frozenset} and satisfied_gates <= GATES.keys(), "GATE_IDENTITIES")
    exclusions = []
    if selection["backend"] != "NATIVE_DOCS": exclusions.append("NOT_R2_AUTHORITY")
    if selection["platform"] == "OTHER": exclusions.append("PLATFORM_UNQUALIFIED")
    if selection["editor_trust"] != "AUTHORIZED_COOPERATIVE": exclusions.append("NO_FIELD_ACL_ISOLATION")
    if selection["workload_trust"] != "OWNER_AUTHORIZED": exclusions.append("NO_HOSTILE_WORKLOAD_SANDBOX")
    needed = set(COMMON_GATES)
    platform = selection["platform"].lower()
    if platform in {"windows","linux"}:
        needed |= {"protected_credentials_"+platform,"native_"+platform+"_identity"}
        if selection["launcher"] != "NONE": needed.add(platform+"_fixed_launch")
    needed.add("same_host_roles" if selection["topology"] == "SAME_HOST" else "separate_hosts")
    if selection["launcher"] == "NONE": needed.add("no_launcher_idle")
    if selection["session"] in {"SERVICE","HEADLESS"}: needed.add("headless_session")
    if selection["wake"] != "NONE": needed.add("wake_topology")
    if selection["network_change"] != "NONE": needed.add("network_change_capability")
    missing = sorted(needed - satisfied_gates)
    return dict(decision="UNSUPPORTED_MODE" if exclusions else ("BLOCKED_BY_EVIDENCE" if missing else "MODEL_REQUIREMENTS_SATISFIED"),
                exclusions=exclusions, required_gates=sorted(needed), missing_gates=missing,
                release_authorization=False, runtime_activation=False)


def parse_control(raw):
    require(type(raw) is bytes and len(raw) <= MAX_DOCUMENT_BYTES, "CONTROL_SIZE")
    def pairs(items):
        value = {}
        for key, child in items:
            require(key not in value, "DUPLICATE_KEY")
            value[key] = child
        return value
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(PolicyError("NONFINITE_JSON")))
    except (UnicodeError, ValueError, RecursionError):
        raise PolicyError("CONTROL_PARSE") from None
    require(type(value) is dict, "CONTROL_SHAPE")
    stack, count = [(value,0)], 0
    while stack:
        node, depth = stack.pop(); count += 1
        require(depth <= 32 and count <= 50000, "CONTROL_COMPLEXITY")
        if type(node) is dict:
            stack.extend((child,depth+1) for child in node.values())
            stack.extend((key,depth+1) for key in node)
        elif type(node) is list:
            stack.extend((child,depth+1) for child in node)
        elif type(node) is str:
            try: node.encode("utf-8")
            except UnicodeError: raise PolicyError("CONTROL_ENCODING") from None
        elif type(node) is float:
            require(math.isfinite(node), "NONFINITE_JSON")
    # Successful parsing is not business schema, authorization or identity proof.
    return value


SUFFIXES = {"python":".py", "python3":".py", "pwsh":".ps1", "powershell":".ps1", "bash":".sh", "sh":".sh"}
MAX_ARTIFACT_BYTES = 8388608


def artifact_policy(descriptor, data, expected_binding, expected_slot):
    fields = {"binding", "kind", "slot", "size_bytes", "sha256", "complete", "interpreter", "suffix"}
    require(type(descriptor) is dict and set(descriptor) == fields, "DESCRIPTOR_SHAPE")
    try:
        validate_shape("binding", descriptor["binding"])
    except ContractError:
        raise PolicyError("DESCRIPTOR_BINDING") from None
    require(descriptor["binding"] == expected_binding, "DESCRIPTOR_BINDING")
    kind = descriptor["kind"]
    require(type(kind) is str and kind in {"INPUT","OUTPUT"}, "ARTIFACT_KIND")
    slot = descriptor["slot"]
    require(type(slot) is str and slot == expected_slot
            and re.fullmatch(r"artifact\.[0-9]{3}\." + kind.lower(), slot) is not None, "ARTIFACT_SLOT")
    require(int(slot.split(".")[1]) < 64, "ARTIFACT_SLOT")
    size = descriptor["size_bytes"]
    require(type(size) is int and (1 if kind == "INPUT" else 0) <= size <= MAX_ARTIFACT_BYTES, "ARTIFACT_SIZE")
    require(descriptor["complete"] is True and type(data) is bytes and len(data) == size, "ARTIFACT_INCOMPLETE")
    sha = descriptor["sha256"]
    require(type(sha) is str and re.fullmatch(r"[a-f0-9]{64}",sha) is not None
            and hashlib.sha256(data).hexdigest() == sha, "ARTIFACT_INTEGRITY")
    if kind == "INPUT":
        require(sha == expected_binding["payload_sha256"], "PAYLOAD_INTEGRITY")
        interpreter = descriptor["interpreter"]
        require(type(interpreter) is str and interpreter in SUFFIXES
                and descriptor["suffix"] == SUFFIXES[interpreter], "INTERPRETER_POLICY")
        name = "fetch-" + hashlib.sha256(encoded(expected_binding)).hexdigest() + SUFFIXES[interpreter]
    else:
        require(descriptor["interpreter"] is None and descriptor["suffix"] is None, "RESULT_IS_DATA")
        name = None
    return dict(kind=kind, local_basename=name, descriptor_is_authorization=False,
                output_is_instruction=False)


def result_data(text):
    require(type(text) is str, "RESULT_SHAPE")
    try: raw = text.encode("utf-8")
    except UnicodeError: raise PolicyError("RESULT_ENCODING") from None
    require(len(raw) <= 512, "RESULT_VIEW_SIZE")
    return dict(trust="UNTRUSTED_RESULT_DATA", text=text, action_authorization=False,
                secret_free_guarantee=False)


def matrix_export():
    return dict(compatibility_status="UNRELEASED", runtime_activation=False,
        rights={action:dict(actors=sorted(actors),required_facts=sorted(BASE|facts)) for action,(actors,facts) in RULES.items()},
        failure={code:failure_policy(code) for code in FAULTS},
        dimensions={key:sorted(values) for key,values in DIMENSIONS.items()},
        evidence_gates=GATES, common_gates=sorted(COMMON_GATES),
        bounds=dict(control_bytes=MAX_DOCUMENT_BYTES,control_depth=32,control_nodes=50000,
                    artifact_bytes=MAX_ARTIFACT_BYTES,result_view_bytes=512))
