import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tb4.network_table import (AddressingObservation, NetworkTableError, SCHEMA_BUNDLE, TABLE_SCHEMA_BUNDLE,
                              addressing_prerequisite, endpoint_digest, notices, parse_proposal,
                              parse_table, render_proposal, render_table, validate)
from tests.network_table_support import CANARY, system, good_proposal, seed


@pytest.fixture
def table(tmp_path):
    return system(tmp_path)[0]


def test_generated_machine_schemas_and_canonical_round_trip(table):
    root = Path(__file__).resolve().parents[2]
    for name, schema in (("network-description-v1.schema.json",SCHEMA_BUNDLE),
                         ("network-table-v1.schema.json",TABLE_SCHEMA_BUNDLE)):
        actual = json.loads((root/"protocol"/name).read_text())
        assert actual == schema
        Draft202012Validator.check_schema(actual)
    raw = render_table(table.read())
    assert render_table(parse_table(raw)) == raw
    proposed = good_proposal(table)
    assert render_proposal(parse_proposal(render_proposal(proposed))) == render_proposal(proposed)


@pytest.mark.parametrize("field",["password","token","private_key","resolver_handle","path","address",
                                   "router_procedure","instruction_url","shell","display_name"])
def test_secret_topology_and_instruction_fields_are_not_description_inputs(table, field):
    proposed = good_proposal(table)
    proposed["description"][field] = CANARY
    with pytest.raises(NetworkTableError) as caught:
        parse_proposal(json.dumps(proposed).encode())
    assert CANARY not in str(caught.value)


@pytest.mark.parametrize("field,value",[
    ("schema_version",True),("expected_revision",True),("expected_revision",0),
    ("device_id","not-an-identity"),("description",{}),("description",None)])
def test_invalid_proposal_identity_revision_and_types(table, field, value):
    proposed = good_proposal(table)
    proposed[field] = value
    with pytest.raises(NetworkTableError):
        parse_proposal(json.dumps(proposed).encode())


@pytest.mark.parametrize("raw",[b'{"schema_version":1,"schema_version":1}',
                                b'{"expected_revision":NaN}', b"[]",b"",b"x"*16385])
def test_duplicate_nonfinite_and_unbounded_proposals_fail_closed(raw):
    with pytest.raises(NetworkTableError):
        parse_proposal(raw)


def test_observations_need_descriptions_and_never_leak_private_hints(table):
    output = notices(table.read()["catalogue"],table.read(),now=100)
    assert output["needs_description"] == 1
    assert output["devices"][0]["description_status"] == "MISSING_DESCRIPTION"
    text = json.dumps(output)
    assert all(secret not in text for secret in (CANARY,"192.0.2.8","synthetic-interface","synthetic-hint"))


@pytest.mark.parametrize("stable_ip",["UNKNOWN","NOT_ASSIGNED","ASSIGNED"])
def test_optional_addressing_does_not_block_adequate_description_or_other_prerequisites(table, stable_ip):
    proposed = good_proposal(table,stable_ip=stable_ip)
    table.approve(proposed,now=100,owner_authorized=True)
    value = table.read()
    row = notices(value["catalogue"],value,now=101)["devices"][0]
    assert row["description_status"] == "DESCRIBED"
    assert row["stable_ip"] == dict(value=stable_ip,source="OWNER_DECLARATION",freshness="FRESH")
    assert addressing_prerequisite(value,proposed["device_id"],required=False,now=101) == "NOT_REQUIRED"
    assert addressing_prerequisite(value,proposed["device_id"],required=True,now=101) == "STABLE_ADDRESS_REQUIRED"


def test_fresh_verified_addressing_is_scoped_to_only_that_action_and_endpoint(table):
    proposed = good_proposal(table)
    device_id = proposed["device_id"]
    entry = table.read()["catalogue"]["entries"][0]
    table.record_addressing(AddressingObservation(device_id,endpoint_digest(entry),"ASSIGNED",100,60),
                            current_owner=lambda:True)
    assert addressing_prerequisite(table.read(),device_id,required=True,now=101) == "SATISFIED"
    assert addressing_prerequisite(table.read(),device_id,required=True,now=160) == "STABLE_ADDRESS_REQUIRED"
    assert addressing_prerequisite(table.read(),device_id,required=True,now=99) == "STABLE_ADDRESS_REQUIRED"
    seed(table,at=102,address="192.0.2.9")
    assert table.read()["catalogue"]["entries"][0]["device_id"] == device_id
    assert addressing_prerequisite(table.read(),device_id,required=True,now=103) == "STABLE_ADDRESS_REQUIRED"


def test_stale_unknown_platform_and_noncomputer_descriptions_are_distinct(table):
    proposed = good_proposal(table)
    proposed["description"].update(roles=["fetcher"],launch_mode={"fetcher":"UNSUPPORTED"})
    table.approve(proposed,now=100,valid_for_s=60,owner_authorized=True)
    status = table.status(now=101)["devices"][0]
    assert status["description_status"] == "INADEQUATE_DESCRIPTION"
    assert status["missing"] == ["platform.architecture","platform.os"]
    assert table.status(now=160)["devices"][0]["description_status"] == "STALE_DESCRIPTION"
    assert table.status(now=99)["devices"][0]["description_status"] == "CLOCK_UNCERTAIN"
    table.approve(good_proposal(table,kind="ROUTER"),now=200,owner_authorized=True)
    assert table.status(now=201)["devices"][0]["description_status"] == "DESCRIBED"


@pytest.mark.parametrize("mutation",["identity","foreign-description","role","extra","revision","duplicate-entry"])
def test_semantic_table_identity_and_schema_errors_are_closed(table,mutation):
    value = copy.deepcopy(table.read())
    if mutation == "identity": value["installation_id"]="00000000-0000-4000-8000-000000000099"
    elif mutation == "foreign-description":
        value["descriptions"]["00000000-0000-4000-8000-000000000099"]={}
    elif mutation == "role":
        table.approve(good_proposal(table),now=100,owner_authorized=True)
        value=table.read();next(iter(value["descriptions"].values()))["description"]["launch_mode"]={"fetcher":"EXTERNAL"}
    elif mutation == "extra": value["credentials"]=CANARY
    elif mutation == "revision": value["revision"]=True
    else: value["catalogue"]["entries"][1]=copy.deepcopy(value["catalogue"]["entries"][0])
    with pytest.raises(NetworkTableError):
        validate(value)

