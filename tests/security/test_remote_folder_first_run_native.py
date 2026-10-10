"""Actual protected Windows/Linux profiles with synthetic remote physical replies."""
from types import SimpleNamespace
import pytest

from tb4.commissioning_checks import CommissionedStorage, detect_environment
from tb4.commissioning_state import Setup, DenyActivation
from tb4.drive.folder_first_run import RemoteFolderCommissioning
from tb4.drive.folder_transport import FixedProcess
from tb4.private_settings import native_settings
from test_private_settings_native import fixture, SUPPORTED
from test_folder_probe import client
from test_folder_first_run import setup_for

pytestmark = pytest.mark.skipif(not SUPPORTED, reason="Actual Windows/Linux protected first-run")


def system(store, monkeypatch):
    probe, calls = client(monkeypatch)
    model, checker = setup_for(store, CommissionedStorage(RemoteFolderCommissioning(probe)),
        environment=lambda: detect_environment(launch_mode="DESKTOP_SESSION"))
    return model, checker, calls


def test_actual_native_restart_rechecks_remote_proof_and_preserves_private_identity_history(fixture, monkeypatch):
    root, store = fixture
    model, checker, calls = system(store, monkeypatch)
    assert model.review(checker)["settings_validated"]
    before = store.read().payload
    def unavailable(*_): raise OSError("SYNTHETIC_PRIVATE_CANARY")
    monkeypatch.setattr(FixedProcess, "call", unavailable)
    restarted = Setup(native_settings(root))
    assert not restarted.status()["settings_validated"]
    assert restarted.review(checker)["reason"] == "STORAGE_UNAVAILABLE"
    after = store.read().payload
    for key in ("installation_id", "setup_nonce", "choices", "operations"):
        assert after[key] == before[key]
    assert len(calls) == 1 and not restarted.status()["runtime_active"]


def test_actual_native_activation_refreshes_remote_access_before_enter(fixture, monkeypatch):
    _, store = fixture
    model, checker, calls = system(store, monkeypatch)
    assert model.review(checker)["settings_validated"]
    identity, nonce, choices = model.installation_id, model._payload["setup_nonce"], model.private_choices()
    def unavailable(*_): raise OSError("SYNTHETIC_PRIVATE_CANARY")
    monkeypatch.setattr(FixedProcess, "call", unavailable)
    entered = []
    result = model.activate(checker, SimpleNamespace(enter=lambda *_: entered.append(True)))
    assert result["reason"] == "STORAGE_UNAVAILABLE" and not entered
    assert model.installation_id == identity and model._payload["setup_nonce"] == nonce
    assert model.private_choices() == choices and model._payload["operations"] == {}
    assert len(calls) == 1


def test_actual_native_unknown_work_blocks_probe_and_replay_after_restart(fixture, monkeypatch):
    root, store = fixture
    model, checker, calls = system(store, monkeypatch)
    invoked = []
    model.perform_once("e" * 64, lambda: invoked.append(True), owner_authorized=True)
    before = store.read().payload
    restarted = Setup(native_settings(root))
    assert restarted.review(checker)["reason"] == "UNKNOWN_OPERATION"
    assert not calls and invoked == [True]
    assert store.read().payload["operations"] == before["operations"] == {"e" * 64: "UNKNOWN"}
    assert not restarted.activate(checker, DenyActivation())["runtime_active"]
    assert not calls and invoked == [True]
