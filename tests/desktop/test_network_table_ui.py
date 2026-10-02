import copy
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6 import QtWidgets

from tb4.desktop.network_table_dialog import NetworkTableDialog,ERROR
from tb4.desktop.setup import SetupController
from tb4.desktop.setup_app import SetupWindow
from tests.network_table_support import CANARY,system,good_proposal


@pytest.fixture(scope="module")
def application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_real_local_editor_reports_missing_approves_optional_ip_and_moves_table(application,tmp_path):
    table,factory=system(tmp_path)
    window=NetworkTableDialog(table)
    try:
        window.show();application.processEvents()
        assert "need a current description" in window.message.text()
        assert CANARY not in window.devices.currentText()
        window.kind.setCurrentIndex(window.kind.findData("ROUTER"))
        window.stable_ip.setCurrentIndex(window.stable_ip.findData("NOT_ASSIGNED"))
        window.approve.click()
        assert table.status(now=int(time.time()))["devices"][0]["description_status"]=="DESCRIBED"
        assert "0 devices" in window.message.text()
        before=table.read()
        destination=tmp_path/"gui-selected"
        window.location.setText(str(destination));window.save_location.click()
        assert table.local_location()==str(destination) and table.read()==before
        assert table.setup.private_choices()["descriptor"] is None
        assert table.setup._payload.get("enrollments") is None
    finally:
        window.close();window.deleteLater();application.processEvents()


def test_editor_keeps_captured_revision_and_private_provider_errors_closed(application,tmp_path):
    table,factory=system(tmp_path);window=NetworkTableDialog(table)
    try:
        window.kind.setCurrentIndex(window.kind.findData("COMPUTER"))
        table.approve(good_proposal(table),now=int(time.time()),owner_authorized=True)
        before=table.read();window.approve.click()
        assert window.message.text()==ERROR and table.read()==before
        assert CANARY not in window.message.text()
    finally:
        window.close();window.deleteLater();application.processEvents()


def test_opening_editor_or_setup_does_not_create_or_move_a_table(application,tmp_path):
    table,factory=system(tmp_path);before=copy.deepcopy(factory.natives)
    # Watchdog/fetcher role control uses actual controller; no live factory.
    controller=SetupController(table.setup,role="watchdog",network_factory=lambda _:table)
    window=SetupWindow(controller)
    dialog=NetworkTableDialog(table)
    try:
        assert window.network.isEnabled()
        assert set(factory.natives)==set(before)
        assert table.setup._payload["network_table"]["pending"] is None
        assert controller.network_session() is table
    finally:
        dialog.close();window.close();dialog.deleteLater();window.deleteLater()
        application.processEvents()

