from __future__ import annotations

import json
import os
import threading
from types import SimpleNamespace

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
QtWidgets = pytest.importorskip('PySide6.QtWidgets')

from tb4.desktop.app import RoleWindow
from tb4.desktop import entry, worker
from tb4.desktop.profile import ProfileError, profile_for


@pytest.fixture
def make_window(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    windows = []

    def make(role='fetcher'):
        window = RoleWindow(profile_for(role, tmp_path), smoke=True)
        window.timer.stop()
        windows.append(window)
        return window

    yield make
    for window in windows:
        window.tray.hide()
        window.deleteLater()
    app.processEvents()


def ticket():
    return {
        'operation_id': 'reviewed-operation', 'generation': 7,
        'result_sha256': 'a' * 64, 'archive_id': 'separate-archive', 'reviewed': True,
    }


def test_recovery_is_fetcher_only(make_window):
    fetcher = make_window('fetcher')
    watchdog = make_window('watchdog')
    assert fetcher.recovery_button is not None
    assert watchdog.recovery_button is None


def test_active_worker_blocks_recovery_before_dialog(make_window, monkeypatch):
    window = make_window()
    monkeypatch.setattr(window, 'client', SimpleNamespace(active=True))
    monkeypatch.setattr(QtWidgets.QInputDialog, 'getMultiLineText', lambda *a: pytest.fail('no dialog during active work'))
    window.recover_return()
    assert 'STOP_FETCHER_BEFORE_RETURN_RECOVERY' in window.history.toPlainText()


@pytest.mark.parametrize('accepted', [False, True])
def test_dialog_cancel_or_invalid_ticket_never_starts_worker(make_window, monkeypatch, accepted):
    window = make_window()
    monkeypatch.setattr(QtWidgets.QInputDialog, 'getMultiLineText', lambda *a: ('{}', accepted))
    monkeypatch.setattr(window, 'start_action', lambda *a: pytest.fail('invalid/unreviewed input must not start'))
    window.recover_return()


@pytest.mark.parametrize('confirm', [False, True])
def test_only_explicit_confirmation_routes_one_ticket(make_window, monkeypatch, confirm):
    window = make_window()
    value = ticket()
    monkeypatch.setattr(QtWidgets.QInputDialog, 'getMultiLineText', lambda *a: (json.dumps(value), True))
    answer = QtWidgets.QMessageBox.StandardButton.Yes if confirm else QtWidgets.QMessageBox.StandardButton.No
    monkeypatch.setattr(QtWidgets.QMessageBox, 'question', lambda *a: answer)
    calls = []
    monkeypatch.setattr(window, 'start_action', lambda *a: calls.append(a))
    window.recover_return()
    assert calls == [('recover-return', value)] if confirm else calls == []


def test_watchdog_worker_cannot_invoke_fetcher_recovery():
    with pytest.raises(ProfileError, match='REQUIRES_FETCHER'):
        worker.run_action(SimpleNamespace(role='watchdog'), 'recover-return', None, threading.Event())


def test_self_test_failure_retains_selected_role(tmp_path, monkeypatch):
    def failure(role):
        raise RuntimeError('test failure')
    monkeypatch.setattr(entry, 'packaged_self_test', failure)
    report = tmp_path / 'report.json'
    result = entry.main('fetcher', ['--action', 'self-test', '--profile-root', str(tmp_path), '--report', str(report)])
    assert result == 1
    assert json.loads(report.read_text(encoding='utf-8'))['role'] == 'fetcher'
