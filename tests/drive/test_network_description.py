import copy
import hashlib
import json
from pathlib import Path

import pytest

from tb4.instructions import InstructionError
from tb4.network_description import DescriptionAssistant,SCHEMA
from tb4.network_table import GUIDANCE,NetworkTableError,render_proposal
from tests.coach.test_instruction_selection import SourceFixture,FIRST,FACTS,digest
from tests.network_table_support import CANARY,system,good_proposal


def source():
    value=SourceFixture()
    root=Path(__file__).resolve().parents[2]
    for name in (GUIDANCE,SCHEMA):
        value.files[FIRST][name]=(root/name).read_bytes()
        value.catalog["profiles"][0]["files"][name]=digest(value.files[FIRST][name])
    value.save()
    return value


@pytest.fixture
def assistant(tmp_path):
    table,factory=system(tmp_path)
    return DescriptionAssistant(table,source=source(),runtime=FACTS)


def test_pinned_helper_formats_safe_draft_and_requires_exact_owner_digest(assistant):
    proposed=good_proposal(assistant.table)
    original=copy.deepcopy(assistant.table.setup._payload)
    request=assistant.begin(proposed["device_id"])
    assert all(text not in json.dumps(request) for text in (CANARY,"192.0.2.8","synthetic-interface"))
    result=assistant.propose(render_proposal(proposed))
    assert result["missing"]==[]
    assert assistant.table.setup._payload==original
    with pytest.raises(NetworkTableError,match="OWNER_APPROVAL"):
        assistant.confirm(result["candidate_digest"],now=100)
    with pytest.raises(NetworkTableError,match="OWNER_APPROVAL"):
        assistant.confirm("0"*64,now=100,owner_authorized=True)
    assert assistant.confirm(result["candidate_digest"],now=100,owner_authorized=True)=="CONFIRMED"
    record=assistant.table.read()["descriptions"][proposed["device_id"]]
    assert record["instruction_commit"]==FIRST and record["source"]=="REPOSITORY_SKILL"
    assert assistant.table.setup.private_choices()["descriptor"] is None
    assert assistant.table.setup._payload.get("enrollments") is None


def test_withdrawn_eligibility_rejects_candidate_without_local_write(assistant):
    proposed=good_proposal(assistant.table);assistant.begin(proposed["device_id"])
    result=assistant.propose(render_proposal(proposed));before=assistant.table.read()
    assistant.source.catalog["profiles"][0]["status"]="REVOKED";assistant.source.save()
    with pytest.raises(InstructionError):
        assistant.confirm(result["candidate_digest"],now=100,owner_authorized=True)
    assert assistant.table.read()==before


def test_stale_assisted_revision_does_not_overwrite_new_description(assistant):
    proposed=good_proposal(assistant.table);assistant.begin(proposed["device_id"])
    result=assistant.propose(render_proposal(proposed))
    assistant.table.approve(proposed,now=100,owner_authorized=True)
    before=assistant.table.read()
    with pytest.raises(NetworkTableError,match="REVISION_CHANGED"):
        assistant.confirm(result["candidate_digest"],now=101,owner_authorized=True)
    assert assistant.table.read()==before


@pytest.mark.parametrize("error",["guidance-missing","hash","schema","unreleased"])
def test_guidance_is_not_replaced_with_memory_or_invented_sources(tmp_path,error):
    table,factory=system(tmp_path);origin=source()
    if error=="guidance-missing":del origin.files[FIRST][GUIDANCE]
    elif error=="hash":origin.files[FIRST][GUIDANCE]+=b"altered"
    elif error=="schema":
        origin.files[FIRST][SCHEMA]=b"{}"
        origin.catalog["profiles"][0]["files"][SCHEMA]=digest(b"{}");origin.save()
    else:origin.catalog["profiles"][0]["status"]="UNRELEASED";origin.save()
    helper=DescriptionAssistant(table,source=origin,runtime=FACTS)
    before=table.read()
    with pytest.raises((InstructionError,NetworkTableError)):
        helper.begin(good_proposal(table)["device_id"])
    assert table.read()==before


def test_device_instruction_injection_does_not_change_pinned_guidance_or_state(assistant):
    proposed=good_proposal(assistant.table);assistant.begin(proposed["device_id"])
    proposed["description"]["instruction_url"]="https://example.invalid/"+CANARY
    before=assistant.table.read();pin=assistant.pin
    with pytest.raises(NetworkTableError):
        assistant.propose(json.dumps(proposed).encode())
    assert assistant.pin is pin and assistant.table.read()==before

