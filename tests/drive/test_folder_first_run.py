"""Portable first-run integration; synthetic replies do not prove physical files."""
from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

from tb4.commissioning_checks import CommissionedStorage, Prerequisites
from tb4.commissioning_state import Setup, DenyActivation
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_first_run import RemoteFolderCommissioning
from tb4.drive.folder_probe import FolderProbe
from tb4.drive.folder_protocol import FolderAccess
from tb4.drive.folder_transport import FixedProcess
from tb4.exchange_layout import Capacity
from tb4.private_settings import PrivateSettings, SettingsError
from test_folder_probe import client, document, SPEC, HANDLE
from test_native_leadership import ACTORS, tid
from tests.security.test_first_run import Source, FACTS, ENVIRONMENT
from tests.security.test_private_settings import MemoryNative
from tests.security.test_ballpark_contract import fixture as descriptor_fixture


def record(spec=SPEC, handle=HANDLE):
    return dict(spec=asdict(spec), authority=handle.record())


def setup_for(store, storage, *, environment=None):
    model = Setup(store, create=True)
    spec = storage.port.spec
    descriptor = descriptor_fixture()
    descriptor["installation_id"] = model.installation_id
    descriptor["domain_id"] = spec.domain_id
    model.choose(dict(role="watchdog", storage=record(spec, storage.port._handle),
                      network_scope=[], descriptor=descriptor))
    checker = Prerequisites(environment=environment or (lambda: ENVIRONMENT),
        storage=storage, credentials=None, source=Source(), runtime=FACTS, clock=lambda: 100)
    return model, checker


def test_actual_first_run_consumes_one_new_proof_per_review_and_keeps_default_activation_closed(monkeypatch):
    probe, calls = client(monkeypatch)
    storage = CommissionedStorage(RemoteFolderCommissioning(probe))
    model, checker = setup_for(PrivateSettings(MemoryNative()), storage)
    identity, nonce = model.installation_id, model._payload["setup_nonce"]
    assert model.review(checker)["settings_validated"]
    assert len(calls) == 1
    assert model.review(checker)["settings_validated"] and len(calls) == 2
    result = model.activate(checker, DenyActivation())
    assert result["reason"] == "ACTIVATION_NOT_AUTHORIZED" and not result["runtime_active"]
    assert len(calls) == 3 and len({c["nonce"] for c in calls}) == 3
    assert model.installation_id == identity and model._payload["setup_nonce"] == nonce
    assert model._payload["operations"] == {}


@pytest.mark.parametrize("change", [
    "root", "domain", "setup", "actor", "capacity", "mode",
    "authority", "authority-root", "tab", "root-transition", "extra", "missing"])
def test_changed_protected_selection_refuses_before_transport(monkeypatch, change):
    probe, calls = client(monkeypatch)
    value = record()
    if change == "root": value["spec"]["root_id"] = SPEC.domain_id
    if change == "domain": value["spec"]["domain_id"] = SPEC.root_id
    if change == "setup": value["spec"]["setup_id"] = tid("foreign-remote-setup")
    if change == "actor": value["spec"]["bootstrap_actor"] = ACTORS[1]
    if change == "capacity": value["spec"]["capacity"] = asdict(Capacity(2, 1, 1, 1))
    if change == "mode": value["spec"]["mode"] = "NATIVE_DOCS"
    if change == "authority": value["authority"]["seal"] = "b" * 64
    if change == "authority-root": value["authority"]["object_id"] = SPEC.domain_id
    if change == "tab": value["authority"]["tab_id"] = "synthetic-tab"
    if change == "root-transition": value["root_transition"] = "a" * 64
    if change == "extra": value["path"] = "SYNTHETIC_PRIVATE_CANARY"
    if change == "missing": del value["authority"]
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"):
        CommissionedStorage(RemoteFolderCommissioning(probe)).verify(value)
    assert not calls


@pytest.mark.parametrize("change", ["spec", "handle", "transport", "origin", "binding"])
def test_changed_trusted_probe_pin_refuses_before_any_io(monkeypatch, change):
    probe, calls = client(monkeypatch)
    storage = CommissionedStorage(RemoteFolderCommissioning(probe))
    if change == "spec": probe.spec = replace(SPEC, setup_id=tid("changed-probe"))
    if change == "handle": probe.handle = replace(HANDLE, seal="b" * 64)
    if change == "transport": probe.transport = FixedProcess(probe.binding, probe.transport.argv)
    if change == "origin": probe._origin = object()
    if change == "binding": probe.binding = SimpleNamespace(root_id=SPEC.root_id, domain_id=SPEC.domain_id)
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$"): storage.verify(record())
    assert not calls


def test_saved_success_is_not_new_first_run_readiness(monkeypatch):
    saved = []
    def replay(value):
        if not saved: saved.append(value)
        return saved[0]
    probe, calls = client(monkeypatch, replay)
    model, checker = setup_for(PrivateSettings(MemoryNative()),
                              CommissionedStorage(RemoteFolderCommissioning(probe)))
    assert model.review(checker)["settings_validated"]
    assert model.review(checker)["reason"] == "STORAGE_UNAVAILABLE"
    assert len(calls) == 2 and model._payload["operations"] == {}


def test_remote_error_is_closed_and_does_not_retry_or_disclose_private_canary(monkeypatch):
    probe, calls = client(monkeypatch, lambda r: {**r, "result": "UNKNOWN", "extra": "SYNTHETIC_PRIVATE_CANARY"})
    with pytest.raises(SettingsError, match="^STORAGE_UNAVAILABLE$") as error:
        CommissionedStorage(RemoteFolderCommissioning(probe)).verify(record())
    assert len(calls) == 1 and "SYNTHETIC_PRIVATE_CANARY" not in str(error.value)


def test_only_exact_probe_type_can_construct_read_only_port(monkeypatch):
    probe, calls = client(monkeypatch)
    with pytest.raises(AuthorityError): RemoteFolderCommissioning(SimpleNamespace(**probe.__dict__))
    class Derived(FolderProbe): pass
    child = Derived(probe.transport, SPEC, HANDLE, FolderAccess(probe.binding, True, True))
    with pytest.raises(AuthorityError): RemoteFolderCommissioning(child)
    port = RemoteFolderCommissioning(probe)
    assert port.spec == SPEC and port.root_id == SPEC.root_id
    assert port.verify(record()) == document()
    assert not any(hasattr(port, name) for name in
                   ("authority", "create", "create_authority", "compare_replace", "seed", "activate"))
    assert len(calls) == 1
