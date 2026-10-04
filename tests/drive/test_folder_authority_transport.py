"""Pure closed authority wire checks and the unchanged fixed SSH policy."""
import base64
from pathlib import Path
import pytest

from tb4.drive.docs_authority import AuthorityError, WriteResult, document_bytes
from tb4.drive.folder_authority import FolderBinding
from tb4.drive.folder_authority_transport import _authority_argv, _request, _response
from tb4.drive.folder_probe_transport import ProbeEndpoint, _argv
from tb4.drive.folder_protocol import header
from tb4.exchange_layout import Capacity, MAX_GENERATION, empty_document, encoded

ROOT = "00000000-0000-4000-8000-000000000240"
DOMAIN = "00000000-0000-4000-8000-000000000241"
TARGET = "00000000-0000-4000-8000-000000000242"
BINDING = FolderBinding(ROOT, DOMAIN)
NONCE = "a" * 32
BODY = base64.b64encode(document_bytes(empty_document(DOMAIN, Capacity(1,1,1,1)))).decode("ascii")


def request(operation="READ"):
    return {**header(BINDING, NONCE), "operation": operation,
            **({"expected":1, "body":BODY} if operation == "CAS" else {})}


def response(operation="READ"):
    return {**header(BINDING, NONCE), **(
        {"result":"SNAPSHOT","revision":1,"body":BODY} if operation == "READ"
        else {"result":WriteResult.ACCEPTED.value})}


def test_normal_authority_argv_changes_only_the_fixed_command_and_accepts_no_caller_command(tmp_path):
    endpoint = ProbeEndpoint(TARGET, "e"*64, str(Path("synthetic-ssh").resolve()),
        "storage.invalid", 22222, "synthetic-user", str(tmp_path/"synthetic-known"), 1)
    key, known = str(tmp_path/"synthetic key%"), str(tmp_path/"synthetic known%")
    normal = _authority_argv(endpoint, key, known)
    probe = _argv(endpoint, key, known)
    assert normal[:-1] == probe[:-1] and normal[-1] == "tb4-folder-v1"
    assert probe[-1] == "tb4-folder-probe-v1"
    assert len(normal) <= 64 and sum(v.startswith("-oIdentityFile=") for v in normal) == 1
    assert "-i" not in normal and "-oIdentityAgent=none" in normal
    with pytest.raises(TypeError): _authority_argv(endpoint, key, known, "arbitrary-command")


@pytest.mark.parametrize("operation", ["READ","CAS"])
def test_only_closed_normal_requests_and_correlated_replies_are_accepted(operation):
    value = request(operation)
    assert _request(BINDING, encoded(value)) == value
    _response(BINDING, encoded(response(operation)), value)


@pytest.mark.parametrize("change", [
    "verify","extra","root","domain","nonce","mode","expected-bool","expected-zero",
    "expected-max","expected-string","body-invalid","body-foreign","read-body"])
def test_invalid_authority_requests_refuse_before_the_transport_boundary(change):
    value = request("CAS") if change.startswith(("expected","body")) else request()
    if change == "verify": value["operation"] = "VERIFY"
    if change == "extra": value["command"] = "SYNTHETIC_PRIVATE_CANARY"
    if change == "root": value["root"] = TARGET
    if change == "domain": value["domain"] = TARGET
    if change == "nonce": value["nonce"] = "b"*31
    if change == "mode": value["mode"] = "UNKNOWN"
    if change == "expected-bool": value["expected"] = True
    if change == "expected-zero": value["expected"] = 0
    if change == "expected-max": value["expected"] = MAX_GENERATION
    if change == "expected-string": value["expected"] = "1"
    if change == "body-invalid": value["body"] = "not-base64"
    if change == "body-foreign":
        value["body"] = base64.b64encode(document_bytes(empty_document(TARGET,Capacity(1,1,1,1)))).decode("ascii")
    if change == "read-body": value["body"] = BODY
    with pytest.raises(AuthorityError): _request(BINDING, encoded(value))


@pytest.mark.parametrize("operation,change", [
    ("READ","nonce"),("READ","extra"),("READ","revision-bool"),("READ","revision-zero"),
    ("READ","revision-max"),("READ","body"),("READ","unknown"),
    ("CAS","nonce"),("CAS","extra"),("CAS","unknown"),("CAS","foreign-result")])
def test_malformed_lost_or_unrelated_reply_cannot_be_a_private_receipt(operation, change):
    value = response(operation)
    if change == "nonce": value["nonce"] = "b"*32
    if change == "extra": value["private"] = "SYNTHETIC_PRIVATE_CANARY"
    if change == "revision-bool": value["revision"] = True
    if change == "revision-zero": value["revision"] = 0
    if change == "revision-max": value["revision"] = MAX_GENERATION + 1
    if change == "body": value["body"] = "not-base64"
    if change == "unknown":
        value = {**header(BINDING, NONCE), "result":"UNKNOWN"}
    if change == "foreign-result": value["result"] = "SUCCEEDED"
    with pytest.raises(AuthorityError): _response(BINDING, encoded(value), request(operation))


@pytest.mark.parametrize("result", [WriteResult.ACCEPTED, WriteResult.REJECTED, WriteResult.UNAVAILABLE])
def test_correlated_cas_reply_keeps_existing_protocol_semantics_without_inventing_confirmation(result):
    _response(BINDING, encoded({**header(BINDING, NONCE),"result":result.value}), request("CAS"))

