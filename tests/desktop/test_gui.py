import os
import tomllib

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

pytest.importorskip('PySide6')
from PySide6 import QtWidgets
from tb4.desktop.app import RoleWindow
from tb4.desktop.profile import profile_for


@pytest.fixture(scope='module')
def application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_two_role_windows_are_independent_and_do_not_start_workers(application, tmp_path):
    windows = [RoleWindow(profile_for(role, tmp_path), smoke=True) for role in ('watchdog', 'fetcher')]
    try:
        assert windows[0].profile.directory != windows[1].profile.directory
        assert 'WATCHDOG' in windows[0].windowTitle()
        assert 'FETCHER' in windows[1].windowTitle()
        assert all(not w.client.active for w in windows)
        assert all('UNKNOWN' in w.summary.text() for w in windows)
        windows[0].set_field('drive', 'root_id', 'explicit-test-root')
        assert tomllib.loads(windows[0].editor.toPlainText())['drive']['root_id'] == 'explicit-test-root'
        assert tomllib.loads(windows[1].editor.toPlainText())['drive']['root_id'] == 'replace-at-deploy-time'
    finally:
        for window in windows:
            window.timer.stop()
            window.tray.hide()
            window.deleteLater()
        application.processEvents()
