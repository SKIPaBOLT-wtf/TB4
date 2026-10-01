"""Real Qt controls with synthetic private storage; native storage is qualified separately."""
from contextlib import contextmanager
import os
from pathlib import Path
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6 import QtWidgets

from tb4.commissioning_state import Setup
from tb4.commissioning_checks import Environment
from tb4.desktop.setup import SetupController
from tb4.desktop.setup_app import SetupStart, SetupWindow, MESSAGES
from tb4.private_settings import PrivateSettings

ENVIRONMENT=Environment("WINDOWS","X64","USER","DESKTOP_SESSION","INTERACTIVE")


class Memory:
    binding={"principal":"synthetic-ui","directory":[3,4]}
    def __init__(self):self.files={}
    @contextmanager
    def locked(self):yield self
    def read(self,name):return self.files.get(name)
    def stage(self,data):
        assert "settings.pending" not in self.files
        self.files["settings.pending"]=data
    def promote(self):self.files["settings.json"]=self.files.pop("settings.pending")


@pytest.fixture(scope="module")
def application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def controller(native=None):
    native=native or Memory()
    setup=Setup(PrivateSettings(native),create=True)
    return native,SetupController(setup,role="watchdog",environment=lambda:ENVIRONMENT)


def finish(application,window):
    deadline=time.monotonic()+5
    while window.job is not None and time.monotonic()<deadline:
        application.processEvents()
        time.sleep(.01)
    assert window.job is None,"bounded Qt check did not finish"


def test_gui_save_cancel_restart_preserves_identity_and_owner_choices(application):
    native,control=controller()
    window=SetupWindow(control)
    try:
        window.show()
        window.location.setText("synthetic-owner-selected-root")
        window.isolated.setChecked(True)
        window.save.click()
        identity=control.setup.installation_id
        assert control.setup.missing_choices()==()
        assert control.setup.private_choices()["storage"] is None
        window.check.click()
        finish(application,window)
        assert window.message.text()==MESSAGES["STORAGE_UNAVAILABLE"]
        assert control.setup.status()["state"]=="BLOCKED"
        window.cancel.click()
        assert window.resume.isEnabled() and not window.check.isEnabled()
        _,restarted=controller(native)
        assert restarted.setup.installation_id==identity
        assert restarted.view()["state"]=="CANCELLED"
        assert restarted.setup.private_choices()["storage_request"]["location"]=="synthetic-owner-selected-root"
        window.resume.click()
        finish(application,window)
        assert control.view()["reason"]=="STORAGE_UNAVAILABLE"
    finally:
        window.close()
        window.deleteLater()
        application.processEvents()


def test_gui_invalid_scope_does_not_replace_saved_choices(application):
    native,control=controller()
    window=SetupWindow(control)
    try:
        before=dict(native.files)
        window.location.setText("synthetic-root")
        window.scope.setText("not a network")
        window.save.click()
        assert native.files==before
        assert "not a network" not in window.message.text()
    finally:
        window.close()
        window.deleteLater()


def test_gui_unknown_cannot_be_bypassed_with_check_or_changed_choices(application):
    _,control=controller()
    control.save_owner_choices(mode="NATIVE_DOCS",location="synthetic-root",scope="",isolated=True)
    calls=[]
    control.setup.perform_once("e"*64,lambda:calls.append(1),owner_authorized=True)
    window=SetupWindow(control)
    try:
        window.check.click()
        finish(application,window)
        assert window.message.text()==MESSAGES["UNKNOWN_OPERATION"]
        window.location.setText("different-root")
        window.save.click()
        assert control.setup.private_choices()["storage_request"]["location"]=="synthetic-root"
        assert calls==[1]
    finally:
        window.close()
        window.deleteLater()


def test_private_location_gate_never_auto_creates_or_repairs(application,tmp_path):
    calls=[]
    def denied(*args,**kwargs):
        calls.append(kwargs)
        raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
    root=tmp_path/"never-created"
    start=SetupStart("fetcher",root,controller_factory=denied)
    try:
        start.show()
        application.processEvents()
        assert not calls and not root.exists()
        start.open.click()
        assert len(calls)==1 and calls[0]==dict(role="fetcher",create=True)
        assert "CANARY" not in start.message.text() and not root.exists()
    finally:
        start.close()
        start.deleteLater()


def test_entry_routes_only_fresh_gui_to_setup_and_preserves_legacy(monkeypatch,tmp_path):
    from tb4.desktop import entry,setup_app,app
    routes=[]
    monkeypatch.setattr(setup_app,"run_setup",lambda role,**kw:routes.append(("setup",role,kw)) or 0)
    monkeypatch.setattr(app,"run_gui",lambda profile,**kw:routes.append(("legacy",profile.role,kw)) or 0)
    args=["--profile-root",str(tmp_path),"--setup-root",str(tmp_path/"private-new")]
    assert entry.main("watchdog",args)==0 and routes[-1][0]=="setup"
    profile=tmp_path/"watchdog"
    profile.mkdir()
    (profile/"config.toml").write_text("existing legacy bytes",encoding="utf-8")
    assert entry.main("watchdog",args)==0 and routes[-1][0]=="legacy"
    assert entry.main("watchdog",["--action","setup",*args])==0 and routes[-1][0]=="setup"
    assert (profile/"config.toml").read_text()=="existing legacy bytes"
    assert not (tmp_path/"private-new").exists()


def test_untrusted_environment_or_provider_text_never_reaches_status(application):
    native=Memory()
    setup=Setup(PrivateSettings(native),create=True)
    def fail():raise RuntimeError("SYNTHETIC_PRIVATE_CANARY")
    control=SetupController(setup,role="watchdog",environment=fail)
    window=SetupWindow(control)
    try:
        assert window.environment_text.text()==MESSAGES["ENVIRONMENT_UNAVAILABLE"]
        assert "CANARY" not in window.message.text()
    finally:
        window.close()
        window.deleteLater()


def test_default_setup_cannot_manufacture_ballpark_publication_context(application):
    _, control = controller()
    window = SetupWindow(control)
    try:
        assert not window.ballpark.isEnabled()
        from tb4.private_settings import SettingsError
        with pytest.raises(SettingsError, match="DESCRIPTOR_REQUIRED"):
            control.ballpark_session()
        assert not control.setup.status()["runtime_active"]
    finally:
        window.close()
        window.deleteLater()
