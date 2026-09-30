from __future__ import annotations

import json
import queue
import time
import tomllib
from pathlib import Path

import tomlkit
from PySide6 import QtCore, QtGui, QtWidgets

from .process import WorkerProcess, worker_command
from .profile import (Profile, ProfileLock, content_digest, default_config,
                      drive_root_id, read_config)
from .telemetry import append_event, diagnostic_report, observation_state


HELP = {
    "AUTH_INTERACTIVE_REQUIRED": "Choose the OAuth client JSON, save the configuration, then click Authorize Drive.",
    "AUTH_MISSING_LOCAL_CREDENTIALS": "The selected OAuth client JSON is missing. Choose the file and save again.",
    "AUTH_INVALID_LOCAL_CREDENTIALS": "The selected local token is invalid. Inspect it privately; no credentials were exported.",
    "AUTH_REFRESH_FAILED": "Token refresh failed. Check connectivity and the account authorization.",
    "AUTH_INTERACTIVE_FAILED": "Authorization failed or timed out. No role was started.",
    "LEGACY_SERVICE_INSTALLED": "A legacy TB4 service is installed for this role. Do not run both launch modes. Inspect/migrate it explicitly; it was not stopped or removed.",
    "SERVICE_PRESENCE_UNCONFIRMED": "The existing service state could not be verified. Startup was refused rather than assuming no conflict.",
    "PROFILE_BUSY": "This role profile is in use by another process. The other role has a separate profile.",
    "CONFIG_CHANGED_RELOAD_REQUIRED": "The configuration changed on disk. Reload before saving; your edit was not written over it.",
    "CONFIG_UNREADABLE": "Save a configuration before starting or checking the role.",
    "OPTIONAL_LOCAL_MOUNT_UNAVAILABLE": "The optional local Drive folder is not visible to this user. This is separate from API authorization.",
    "RETURN_RECOVERY_TICKET_INVALID": "Provide the reviewed operation_id, generation, result_sha256, archive_id and reviewed=true. Do not paste credentials or an entire configuration.",
    "RETURN_RECOVERY_PULSE_FRESH": "A FETCHER heartbeat is still fresh or future-dated. Confirm every FETCHER for this target is stopped and wait for the configured stale/grace interval. Nothing was published.",
    "RETURN_RECOVERY_PUBLICATION_UNCONFIRMED": "The same recorded return needs inspection. Do not clear the channel, submit a new generation, or replay the payload.",
}


class RoleWindow(QtWidgets.QMainWindow):
    def __init__(self, profile: Profile, *, smoke: bool = False) -> None:
        super().__init__()
        self.profile = profile
        self.smoke = smoke
        self.client = WorkerProcess(profile.role)
        self.snapshot = None
        self.digest = None
        self.last_logged = None
        self.restart_requested = False
        self.quit_requested = False
        self.stop_requested_at = None
        self.setWindowTitle(f"TB4 {profile.role.upper()} - configuration and status")
        self.resize(1000, 760)
        self.icon = self._icon()
        self.setWindowIcon(self.icon)
        tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(tabs)

        status_page = QtWidgets.QWidget()
        status_layout = QtWidgets.QVBoxLayout(status_page)
        heading = QtWidgets.QLabel(f"<h2>TB4 {profile.role.upper()}</h2>")
        status_layout.addWidget(heading)
        self.summary = QtWidgets.QLabel("Stopped. No remote observation.")
        self.summary.setWordWrap(True)
        status_layout.addWidget(self.summary)
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        status_layout.addWidget(self.details)
        controls = QtWidgets.QHBoxLayout()
        self.start_button = self._button("Start role", lambda: self.start_action("run"), controls)
        self.stop_button = self._button("Stop safely", self.request_stop, controls)
        self.restart_button = self._button("Restart safely", self.request_restart, controls)
        status_layout.addLayout(controls)
        checks = QtWidgets.QHBoxLayout()
        self._button("Validate config", lambda: self.start_action("validate"), checks)
        self._button("Check Drive and map", lambda: self.start_action("check"), checks)
        self._button("Authorize Drive", lambda: self.start_action("authorize"), checks)
        if profile.role == "watchdog":
            self._button("Initialize selected root", self.bootstrap, checks)
        status_layout.addLayout(checks)
        self.message = QtWidgets.QLabel("A running process is not proof of working Drive communication.")
        self.message.setWordWrap(True)
        status_layout.addWidget(self.message)
        self._button("Export safe diagnostics", self.export_diagnostics, status_layout)
        self.recovery_button = None
        if profile.role == "fetcher":
            self.recovery_button = self._button("Recover recorded return", self.recover_return, status_layout)
        tabs.addTab(status_page, "Status")

        config_page = QtWidgets.QWidget()
        config_layout = QtWidgets.QVBoxLayout(config_page)
        info = QtWidgets.QLabel("Edit identity and target settings below. The entire TOML is preserved, including comments and extension fields. Save validates it before replacing the private file.")
        info.setWordWrap(True)
        config_layout.addWidget(info)
        choices = QtWidgets.QHBoxLayout()
        self._button("Set Drive folder ID / URL", self.choose_root, choices)
        self._button("Choose OAuth client JSON", self.choose_client, choices)
        self._button("Choose local Drive folder", self.choose_mount, choices)
        config_layout.addLayout(choices)
        self.editor = QtWidgets.QPlainTextEdit()
        self.editor.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont))
        config_layout.addWidget(self.editor)
        saves = QtWidgets.QHBoxLayout()
        self._button("Import config", self.import_config, saves)
        self._button("Reload saved", self.load_config, saves)
        self._button("Save and validate", self.save, saves)
        self._button("Restore previous", self.restore_previous, saves)
        config_layout.addLayout(saves)
        config_layout.addWidget(QtWidgets.QLabel("start_role = true starts this role when its tray app opens. The initial value is false."))
        tabs.addTab(config_page, "Configuration")

        self.history = QtWidgets.QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setMaximumBlockCount(300)
        tabs.addTab(self.history, "Event history")

        self.tray = QtWidgets.QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip(f"TB4 {profile.role.upper()}: stopped")
        menu = QtWidgets.QMenu(self)
        menu.addAction("Open status / configuration", self.show_window)
        menu.addAction("Start role", lambda: self.start_action("run"))
        menu.addAction("Stop safely", self.request_stop)
        menu.addSeparator()
        menu.addAction("Exit this role application", self.request_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window() if reason in {
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick} else None)
        self.has_tray = QtWidgets.QSystemTrayIcon.isSystemTrayAvailable()
        if self.has_tray:
            self.tray.show()
        else:
            self.message.setText("No system tray is available. Keep this window open to monitor the role.")
        self.load_config()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(250)
        self.refresh()
        if not smoke:
            try:
                config = tomllib.loads(self.editor.toPlainText())
                if self.profile.config.is_file() and config.get("desktop", {}).get("start_role") is True:
                    QtCore.QTimer.singleShot(0, lambda: self.start_action("run"))
            except ValueError:
                pass

    def _icon(self):
        image = QtGui.QPixmap(64, 64)
        image.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(image)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.palette().highlight())
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawRoundedRect(2, 2, 60, 60, 12, 12)
        painter.setPen(self.palette().highlightedText().color())
        font = self.font()
        font.setPixelSize(38)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(image.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, self.profile.role[0].upper())
        painter.end()
        return QtGui.QIcon(image)

    @staticmethod
    def _button(text, slot, layout):
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(slot)
        layout.addWidget(button)
        return button

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def error(self, code: str):
        self.message.setText(HELP.get(code, f"{code}. See the startup stage and last API outcome in Status. No automatic reset or retry was performed."))
        self.history.appendPlainText(code)

    def load_config(self):
        try:
            text = read_config(self.profile.config) if self.profile.config.exists() else default_config(self.profile)
            self.digest = content_digest(text) if self.profile.config.exists() else None
            self.editor.setPlainText(text)
        except Exception:
            self.error("CONFIG_UNREADABLE")

    def set_field(self, table: str, key: str, value):
        try:
            document = tomlkit.parse(self.editor.toPlainText())
            if table not in document:
                document[table] = tomlkit.table()
            document[table][key] = value
            self.editor.setPlainText(tomlkit.dumps(document))
        except Exception:
            self.error("FIX_TOML_BEFORE_USING_FIELD_CHOOSER")

    def choose_root(self):
        value, accepted = QtWidgets.QInputDialog.getText(self, "Existing Drive root", "Paste the existing folder ID or its Google Drive folder URL:")
        if accepted:
            try:
                self.set_field("drive", "root_id", drive_root_id(value))
            except ValueError:
                self.error("DRIVE_ROOT_ID_REQUIRED")

    def choose_client(self):
        name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "OAuth client JSON (not a token)", "", "JSON files (*.json)")
        if name:
            self.set_field("drive", "client_secrets_path", name)

    def choose_mount(self):
        name = QtWidgets.QFileDialog.getExistingDirectory(self, "Optional local Drive folder - not the API root ID")
        if name:
            self.set_field("desktop", "local_drive_folder", name)

    def import_config(self):
        if self.client.active:
            self.error("STOP_ROLE_BEFORE_EDITING")
            return
        name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import configuration into this role profile", "", "TOML files (*.toml)")
        if name:
            try:
                self.editor.setPlainText(read_config(Path(name)))
            except Exception:
                self.error("CONFIG_UNREADABLE")

    def save(self):
        if self.client.active:
            self.error("STOP_ROLE_BEFORE_EDITING")
            return
        self.start_action("save", {"text": self.editor.toPlainText(), "expected_digest": self.digest})

    def restore_previous(self):
        if self.client.active:
            self.error("STOP_ROLE_BEFORE_EDITING")
            return
        try:
            text = read_config(self.profile.backup)
        except Exception:
            self.error("BACKUP_UNAVAILABLE")
            return
        answer = QtWidgets.QMessageBox.question(self, "Restore previous configuration", "Validate and restore the previous private configuration? The current version becomes the backup.")
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            self.start_action("save", {"text": text, "expected_digest": self.digest})

    def bootstrap(self):
        if self.client.active:
            self.error("STOP_ROLE_BEFORE_INITIALIZATION")
            return
        answer = QtWidgets.QMessageBox.question(self, "Initialize selected existing Drive root", "Create/reconcile the canonical TB4 tree INSIDE the root in the saved configuration? No second root will be created. This changes Drive and is not a connectivity-only check.")
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            self.start_action("bootstrap")

    def recover_return(self):
        if self.profile.role != "fetcher" or self.client.active:
            self.error("STOP_FETCHER_BEFORE_RETURN_RECOVERY")
            return
        text, accepted = QtWidgets.QInputDialog.getMultiLineText(
            self, "Recover a reviewed recorded return",
            "Stop all FETCHER instances for this target first. Paste a reviewed JSON ticket with operation_id, generation, result_sha256, archive_id and reviewed=true. The archive must be a separate matching BONEYARD copy. No credentials:", "",
        )
        if not accepted:
            return
        from tb4.fetcher.return_recovery import ReturnRecoveryError, validate_ticket
        try:
            if len(text) > 4096:
                raise ValueError("ticket too large")
            ticket = validate_ticket(json.loads(text))
        except (ValueError, ReturnRecoveryError):
            self.error("RETURN_RECOVERY_TICKET_INVALID")
            return
        answer = QtWidgets.QMessageBox.question(
            self, "Finalize recorded result without replay",
            f"Publish the already-recorded result for {ticket['operation_id']} (generation {ticket['generation']})?\n\nThis verifies the reviewed report and archive, not whether the result achieved your goal. It does not run the payload, change the report, clear STOP_BALL, or make the channel READY. Confirm the previous execution is no longer running.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            self.start_action("recover-return", ticket)

    def start_action(self, action: str, payload: dict | None = None):
        if self.client.active:
            self.error("WORKER_ALREADY_RUNNING")
            return
        self.snapshot = None
        self.stop_requested_at = None
        try:
            self.client.start(worker_command(self.profile, action), action, payload)
            self.message.setText(f"{action}: starting a separate worker process.")
        except (OSError, ValueError, RuntimeError):
            self.error("WORKER_LAUNCH_FAILED")
        self.refresh()

    def request_stop(self):
        if self.client.active and self.stop_requested_at is None:
            self.stop_requested_at = time.monotonic()
            self.client.request_stop()
            self.message.setText("Cooperative stop requested. FETCHER may cancel active work and report partial effects. Waiting for confirmed exit; no force-kill or replay.")

    def request_restart(self):
        if self.client.active and self.client.action == "run":
            self.restart_requested = True
            self.request_stop()
        elif not self.client.active:
            self.start_action("run")

    def request_quit(self):
        self.restart_requested = False
        self.quit_requested = True
        if self.client.active:
            self.request_stop()
            self.show_window()
        else:
            self.tray.hide()
            QtWidgets.QApplication.instance().quit()

    def export_diagnostics(self):
        name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save redacted diagnostic report", f"tb4-{self.profile.role}-diagnostics.json", "JSON files (*.json)")
        if name:
            try:
                report = diagnostic_report(self.profile.role, self.snapshot, time.time())
                Path(name).write_text(json.dumps(report, indent=2), encoding="utf-8")
                self.message.setText("Diagnostic report saved without configuration, payloads or credential contents.")
            except Exception:
                self.error("DIAGNOSTIC_EXPORT_FAILED")

    def refresh(self):
        for _ in range(40):
            try:
                event = self.client.events.get_nowait()
            except queue.Empty:
                break
            if event.get("session") != self.client.session:
                continue
            if event["kind"] == "snapshot":
                self.snapshot = event["snapshot"]
                semantic = {k: v for k, v in self.snapshot.items() if k not in {"observed_at", "last_drive_at"}}
                if semantic != self.last_logged:
                    self.last_logged = semantic
                    self.history.appendPlainText(json.dumps(semantic, sort_keys=True))
                    try:
                        append_event(self.profile.log, self.snapshot)
                    except Exception:
                        self.error("LOCAL_EVENT_LOG_UNAVAILABLE")
                if self.snapshot.get("error_code"):
                    self.error(self.snapshot["error_code"])
            elif event["kind"] == "error":
                self.error(event["code"])
            elif event["kind"] == "exit":
                self.message.setText(f"{event['action']} exited with code {event['code']}.")
                if event["code"] != 0 and self.snapshot and self.snapshot.get("error_code"):
                    self.error(self.snapshot["error_code"])
                if event["code"] == 0 and event["action"] == "save":
                    self.load_config()
                if self.snapshot is not None:
                    self.snapshot["process_state"] = "EXITED" if event["code"] == 0 else "FAILED"
                if self.quit_requested:
                    self.request_quit()
                elif self.restart_requested:
                    self.restart_requested = False
                    if event["code"] == 0:
                        self.start_action("run")
                    else:
                        self.error("RESTART_REFUSED_AFTER_UNCONFIRMED_STOP")
        active = self.client.active
        self.start_button.setEnabled(not active)
        self.stop_button.setEnabled(active and self.stop_requested_at is None)
        self.restart_button.setEnabled(self.client.action in {None, "run"} and self.stop_requested_at is None)
        if self.recovery_button is not None:
            self.recovery_button.setEnabled(not active)
        remote = observation_state(self.snapshot, time.time())
        process = self.snapshot.get("process_state", "STARTING") if self.snapshot else ("STARTING" if active else "STOPPED")
        if not active and process in {"STARTING", "RUNNING", "STOPPING"}:
            process = "EXITED_UNCONFIRMED"
        self.summary.setText(f"Process: {process} | Last API observation: {remote}")
        self.tray.setToolTip(f"TB4 {self.profile.role.upper()}: {process}; API {remote}")
        detail = dict(self.snapshot or {})
        if detail.get("last_drive_at") is not None:
            detail["last_api_response_age_seconds"] = round(time.time() - detail["last_drive_at"], 1)
        self.details.setPlainText(json.dumps(detail, indent=2))
        if active and self.stop_requested_at is not None and time.monotonic() - self.stop_requested_at > 30:
            self.message.setText("Stop is still unconfirmed. The UI is responsive, but the worker may be waiting for a bounded provider request. No force-kill, root reset or replay was performed.")

    def closeEvent(self, event):
        event.ignore()
        if self.has_tray:
            self.hide()
        else:
            self.request_quit()


def run_gui(profile: Profile, *, smoke_report: Path | None = None, smoke: bool = False) -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(f"TB4 {profile.role.upper()}")
    try:
        with ProfileLock(profile, "gui"):
            window = RoleWindow(profile, smoke=smoke)
            window.show()
            if smoke:
                def finish():
                    if smoke_report:
                        smoke_report.write_text(json.dumps({"role": profile.role, "gui_smoke": "PASS", "tray_available": window.has_tray, "worker_started": window.client.active}), encoding="utf-8")
                    window.timer.stop()
                    window.tray.hide()
                    app.quit()
                QtCore.QTimer.singleShot(150, finish)
            return app.exec()
    except Exception as exc:
        if smoke:
            if smoke_report:
                smoke_report.write_text(json.dumps({"role": profile.role, "gui_smoke": "FAIL", "error_class": type(exc).__name__}), encoding="utf-8")
            return 1
        QtWidgets.QMessageBox.warning(None, "TB4 application could not start", "This role may already be open, or its local profile/GUI dependencies are unavailable. No worker was started.")
        return 1
