"""Model restart on actual protected files; never a live deployment."""
import sys
import json
from contextlib import contextmanager

import pytest

from tb4.commissioning_state import Setup
from tb4.commissioning_checks import detect_environment
from tb4.private_settings import native_settings, SettingsError
from tb4.desktop.setup import open_setup
from test_private_settings_native import fixture


def test_actual_native_model_restart_preserves_identity_and_cancellation(fixture):
    root, store = fixture
    first = Setup(store, create=True)
    first.choose({"role":"fetcher", "network_scope":[]})
    identity = first.installation_id
    first.cancel()
    restarted = Setup(native_settings(root))
    assert restarted.installation_id == identity and restarted.status()["state"] == "CANCELLED"
    restarted.resume()
    assert restarted.missing_choices() == ("storage",)
    assert not restarted.status()["settings_validated"]


def test_actual_environment_probe_reports_only_closed_nonidentifying_facts():
    environment = detect_environment(launch_mode="DESKTOP_SESSION")
    assert environment.os == ("WINDOWS" if sys.platform == "win32" else "LINUX")
    assert environment.architecture in {"X64","ARM64"}
    assert environment.privilege in {"ROOT","ELEVATED","USER"}
    assert environment.launch_mode == "DESKTOP_SESSION"
    assert environment.session in {"INTERACTIVE","NONINTERACTIVE_OR_LOCKED","UNQUALIFIED"}


@pytest.mark.parametrize("phase", ["first-identity", "cancel-unknown"])
def test_desktop_reopen_recovers_same_complete_candidate(fixture, phase):
    root,store=fixture
    calls=[]
    if phase=="cancel-unknown":
        model=Setup(store,create=True)
        model.choose(dict(role="watchdog", network_scope=[],
                          storage_request=dict(mode="NATIVE_DOCS",location="synthetic-root")))
        model.perform_once("e"*64,lambda:calls.append(1),owner_authorized=True)
    original=store.native.locked
    @contextmanager
    def interrupted():
        with original() as port:
            def stop():raise OSError("SYNTHETIC_INTERRUPTION")
            port.promote=stop
            yield port
    store.native.locked=interrupted
    with pytest.raises(SettingsError):
        Setup(store,create=True) if phase=="first-identity" else model.cancel()
    candidate=json.loads((root/"settings.pending").read_bytes())["payload"]
    reopened=open_setup(root,role="watchdog")
    assert reopened.setup.installation_id==candidate["installation_id"]
    assert reopened.setup._payload["setup_nonce"]==candidate["setup_nonce"]
    assert reopened.setup._payload["operations"]==candidate["operations"]
    assert not (root/"settings.pending").exists()
    if phase=="cancel-unknown":
        assert reopened.view()["state"]=="CANCELLED" and calls==[1]
        assert reopened.setup._payload["operations"]=={"e"*64:"UNKNOWN"}
    assert open_setup(root,role="watchdog").setup.installation_id==reopened.setup.installation_id


def test_desktop_reopen_never_repairs_partial_staging_or_empty_identity(fixture):
    root,store=fixture
    with pytest.raises(SettingsError,match="NOT_CREATED"):
        open_setup(root,role="watchdog")
    with store.native.locked() as port:
        port.stage(b"{")
    with pytest.raises(SettingsError):
        open_setup(root,role="watchdog")
    assert (root/"settings.pending").read_bytes()==b"{"
    assert not (root/"settings.json").exists()
