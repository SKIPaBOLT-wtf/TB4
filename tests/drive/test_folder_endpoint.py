"""Closed private endpoint frames; these portable cases do not prove native storage."""
import copy
from dataclasses import asdict
from pathlib import Path
import sys

import pytest

from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import FolderBinding
from tb4.drive.folder_endpoint import EndpointSelection, NativeFolderEndpoint, _shape
from tb4.drive.folder_probe_transport import ProbeEndpoint
from tb4.private_settings import PrivateSettings
from tests.security.test_private_settings import MemoryNative

INSTALLATION = "00000000-0000-4000-8000-000000000260"
BINDING = FolderBinding("00000000-0000-4000-8000-000000000261",
    "00000000-0000-4000-8000-000000000262")
TARGET = "00000000-0000-4000-8000-000000000263"
TRUST = "d" * 64


def frame():
    endpoint = ProbeEndpoint(TARGET, TRUST, str(Path(sys.executable).resolve()),
        "storage.invalid", 22222, "synthetic-user",
        str(Path(sys.executable).resolve().parent / "synthetic-known"), 7)
    return dict(schema_version=1, kind="NATIVE_FOLDER_ENDPOINT", reference="fe_" + "a"*32,
        installation_id=INSTALLATION, authority=asdict(BINDING), blueprint_sha256="b"*64,
        authority_handle_sha256="c"*64, credential_handle="cr_"+"d"*32,
        endpoint=asdict(endpoint), store_binding="e"*64)


def test_closed_frame_is_copied_and_private_selection_repr_has_no_values():
    value = frame()
    result = _shape(value)
    assert result == value and result is not value and result["endpoint"] is not value["endpoint"]
    selection = EndpointSelection(value["reference"], ProbeEndpoint(**value["endpoint"]),
        value["credential_handle"], BINDING)
    assert all(v not in repr(selection) for v in ("storage.invalid", "synthetic-user",
        value["endpoint"]["known_hosts"], value["reference"], value["credential_handle"], TRUST))


@pytest.mark.parametrize("change", [
    "extra", "missing", "version-bool", "version", "kind", "reference", "installation",
    "authority-extra", "authority-root", "blueprint", "handle-hash", "credential",
    "store-binding", "endpoint-extra", "endpoint-host", "port-bool", "port-zero",
    "known-bool", "known-zero", "timeout-bool", "timeout-infinite", "endpoint-password"])
def test_invalid_frame_is_rejected_without_private_value_diagnostics(change):
    value = frame()
    if change == "extra": value["extra"] = "SYNTHETIC_PRIVATE_CANARY"
    if change == "missing": del value["endpoint"]
    if change == "version-bool": value["schema_version"] = True
    if change == "version": value["schema_version"] = 2
    if change == "kind": value["kind"] = "FOLDER_PATH_MAPPING"
    if change == "reference": value["reference"] = "cr_"+"a"*32
    if change == "installation": value["installation_id"] = "foreign"
    if change == "authority-extra": value["authority"]["extra"] = True
    if change == "authority-root": value["authority"]["root_id"] = "foreign"
    if change == "blueprint": value["blueprint_sha256"] = "short"
    if change == "handle-hash": value["authority_handle_sha256"] = "Z"*64
    if change == "credential": value["credential_handle"] = "fe_"+"d"*32
    if change == "store-binding": value["store_binding"] = True
    if change == "endpoint-extra": value["endpoint"]["command"] = "SYNTHETIC_PRIVATE_CANARY"
    if change == "endpoint-host": value["endpoint"]["host"] = "-synthetic"
    if change == "port-bool": value["endpoint"]["port"] = True
    if change == "port-zero": value["endpoint"]["port"] = 0
    if change == "known-bool": value["endpoint"]["known_version"] = True
    if change == "known-zero": value["endpoint"]["known_version"] = 0
    if change == "timeout-bool": value["endpoint"]["timeout"] = True
    if change == "timeout-infinite": value["endpoint"]["timeout"] = float("inf")
    if change == "endpoint-password": value["endpoint"]["password"] = "SYNTHETIC_PRIVATE_CANARY"
    with pytest.raises(AuthorityError) as caught:
        _shape(value)
    assert "SYNTHETIC" not in str(caught.value)


def test_memory_store_is_denied_before_any_native_or_transport_use():
    with pytest.raises(AuthorityError, match="^FOLDER_ENDPOINT_STORE$"):
        NativeFolderEndpoint(PrivateSettings(MemoryNative()), INSTALLATION)
