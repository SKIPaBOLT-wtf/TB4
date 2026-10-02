"""Local first-run Qt workflow. Provider IO runs outside the GUI thread."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile

from PySide6 import QtCore, QtWidgets

from tb4.commissioning_checks import Environment
from tb4.private_settings import SettingsError
from .setup import open_setup

MESSAGES = {
    "MISSING_CHOICES":"Complete the missing setup choices.",
    "REVALIDATION_REQUIRED":"Saved choices are available. Check access before continuing.",
    "CANCELLED":"Setup is cancelled. Your saved identity and choices are preserved.",
    "UNKNOWN_OPERATION":"An earlier operation needs inspection. It will not be repeated.",
    "ENVIRONMENT_UNAVAILABLE":"This environment could not be verified.",
    "STORAGE_UNAVAILABLE":"The selected shared storage connection is not ready or could not be verified.",
    "CREDENTIAL_UNAVAILABLE":"Selected local access is unavailable. Check the original local credential.",
    "DESCRIPTOR_REQUIRED":"Environment collection and its private descriptor are still required.",
    "DESCRIPTOR_INVALID":"The environment descriptor could not be verified.",
    "INSTRUCTIONS_UNAVAILABLE":"A compatible released instruction set is not available.",
    "SETTINGS_VALIDATED":"Setup settings passed their checks. Runtime authorization is separate.",
    "ACTIVATION_NOT_AUTHORIZED":"This build is not authorized to start an R2 runtime.",
    "ACTIVATION_UNKNOWN":"Runtime activation needs inspection. Do not repeat it automatically.",
    "SETTINGS_CHANGED_RELOAD_REQUIRED":"Settings changed in another process. Reopen setup.",
}
ERROR_MESSAGE = "The change could not be saved or verified. Existing data was preserved."


def plain_label(text):
    label = QtWidgets.QLabel(text)
    label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class CheckJob(QtCore.QThread):
    result = QtCore.Signal(dict)
    def __init__(self, controller, action, parent):
        super().__init__(parent)
        self.controller, self.action = controller, action
    def run(self):
        try:
            value = getattr(self.controller,self.action)()
        except Exception:
            value = dict(state="BLOCKED",reason="SETTINGS_CHANGED_RELOAD_REQUIRED",
                         settings_validated=False,runtime_active=False)
        self.result.emit(value)


class SetupWindow(QtWidgets.QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller, self.job = controller, None
        self.setWindowTitle("TB4 " + controller.role.upper() + " — first-run setup")
        self.resize(650,520)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(plain_label("Review the detected environment and save the choices this installation needs."))
        environment = controller.environment
        if type(environment) is Environment:
            facts = asdict(environment)
            self.environment_text = plain_label(" · ".join(facts.values()))
        else:
            self.environment_text = plain_label(MESSAGES["ENVIRONMENT_UNAVAILABLE"])
        layout.addWidget(self.environment_text)
        choices = controller.setup.private_choices()
        request = choices.get("storage_request")
        self.mode = QtWidgets.QComboBox()
        self.mode.addItem("Google Drive folder","NATIVE_DOCS")
        self.mode.addItem("Qualified shared folder","FOLDER_SQLITE_V1")
        self.location = QtWidgets.QLineEdit()
        self.location.setMaxLength(4096)
        self.location.setPlaceholderText("Selected folder URL, ID or qualified location")
        if request is not None:
            self.mode.setCurrentIndex(self.mode.findData(request["mode"]))
            self.location.setText(request["location"])
        elif choices["storage"] is not None:
            self.mode.setCurrentIndex(self.mode.findData(choices["storage"]["spec"]["mode"]))
            self.location.setText(choices["storage"]["spec"]["root_id"])
        self.scope = QtWidgets.QLineEdit()
        self.scope.setMaxLength(4096)
        self.scope.setPlaceholderText("For example: 192.0.2.0/24")
        if choices["network_scope"]:
            self.scope.setText(", ".join(choices["network_scope"]))
        self.isolated = QtWidgets.QCheckBox("Keep network operations disabled")
        self.isolated.setChecked(choices["network_scope"] == [])
        self.isolated.toggled.connect(self._scope_enabled)
        form = QtWidgets.QFormLayout()
        form.addRow("Shared storage", self.mode)
        form.addRow("Folder", self.location)
        form.addRow("Networks TB4 may use", self.scope)
        form.addRow("",self.isolated)
        layout.addLayout(form)
        layout.addWidget(plain_label("Saved selections are local. Shared storage, access and compatibility must be verified before work."))
        self.targets = QtWidgets.QComboBox()
        for target in controller.credential_targets:
            self.targets.addItem(target.label)
        self.credential = QtWidgets.QPushButton("Select existing local key")
        self.credential.clicked.connect(self.select_key)
        if controller.credential_targets:
            form.addRow("Approved remote target",self.targets)
            layout.addWidget(self.credential)
        else:
            self.targets.hide()
            self.credential.hide()
        self.message = plain_label("")
        layout.addWidget(self.message)
        self.ballpark = QtWidgets.QPushButton("Review environment")
        self.ballpark.setEnabled(controller.role == "watchdog" and callable(controller.ballpark_factory))
        self.ballpark.setToolTip("Available after discovery and compatible setup guidance are connected.")
        self.ballpark.clicked.connect(self.review_ballpark)
        layout.addWidget(self.ballpark)
        self.network = QtWidgets.QPushButton("Network devices and table location")
        self.network.setEnabled(controller.role == "watchdog")
        self.network.clicked.connect(self.review_network)
        layout.addWidget(self.network)
        buttons = QtWidgets.QHBoxLayout()
        self.save = QtWidgets.QPushButton("Save choices")
        self.check = QtWidgets.QPushButton("Check setup")
        self.cancel = QtWidgets.QPushButton("Cancel setup")
        self.resume = QtWidgets.QPushButton("Resume setup")
        self.save.clicked.connect(self.save_choices)
        self.check.clicked.connect(lambda:self.start_check("refresh"))
        self.cancel.clicked.connect(self.cancel_setup)
        self.resume.clicked.connect(lambda:self.start_check("resume"))
        for button in (self.save,self.check,self.cancel,self.resume):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self._scope_enabled(self.isolated.isChecked())
        self.show_status(controller.view())

    def _scope_enabled(self, isolated):
        self.scope.setEnabled(not isolated and self.job is None)
        if isolated:
            self.scope.clear()

    def show_status(self, status):
        self.message.setText(MESSAGES.get(status.get("reason"),ERROR_MESSAGE))
        self.resume.setEnabled(status.get("state") == "CANCELLED" and self.job is None)
        self.check.setEnabled(status.get("state") != "CANCELLED" and self.job is None)

    def save_choices(self):
        try:
            result = self.controller.save_owner_choices(mode=self.mode.currentData(),
                location=self.location.text(),scope=self.scope.text(),isolated=self.isolated.isChecked())
            self.show_status(result)
        except Exception:
            self.message.setText(ERROR_MESSAGE)

    def select_key(self):
        selected,_ = QtWidgets.QFileDialog.getOpenFileName(self,"Select an existing local key")
        if not selected:
            return
        try:
            self.show_status(self.controller.select_credential(self.targets.currentIndex(),Path(selected)))
        except Exception:
            self.message.setText(MESSAGES["CREDENTIAL_UNAVAILABLE"])

    def cancel_setup(self):
        try:
            self.show_status(self.controller.cancel())
        except Exception:
            self.message.setText(ERROR_MESSAGE)

    def review_ballpark(self):
        if self.job is not None:
            return
        try:
            from .ballpark_dialog import BallparkDialog
            dialog = BallparkDialog(self.controller.ballpark_session(), self)
            dialog.exec()
            dialog.deleteLater()
            self.show_status(self.controller.view())
        except Exception:
            self.message.setText(MESSAGES["DESCRIPTOR_REQUIRED"])

    def review_network(self):
        if self.job is not None:
            return
        try:
            from .network_table_dialog import NetworkTableDialog
            dialog = NetworkTableDialog(self.controller.network_session(), self)
            dialog.exec()
            dialog.deleteLater()
        except Exception:
            self.message.setText("The network table needs a verified storage identity and a private local location.")

    def start_check(self, action):
        if self.job is not None:
            return
        self.job = CheckJob(self.controller,action,self)
        for widget in (self.mode,self.location,self.scope,self.isolated,self.targets,self.credential,
                       self.save,self.check,self.cancel,self.resume,self.ballpark,self.network):
            widget.setEnabled(False)
        self.message.setText("Checking the saved setup…")
        self.job.result.connect(self.show_status)
        self.job.finished.connect(self.check_finished)
        self.job.start()

    def check_finished(self):
        job,self.job = self.job,None
        job.deleteLater()
        for widget in (self.mode,self.location,self.isolated,self.targets,self.credential,
                       self.save,self.cancel):
            widget.setEnabled(True)
        self._scope_enabled(self.isolated.isChecked())
        self.ballpark.setEnabled(self.controller.role == "watchdog" and callable(self.controller.ballpark_factory))
        self.network.setEnabled(self.controller.role == "watchdog")
        self.show_status(self.controller.view())

    def closeEvent(self, event):
        if self.job is not None and self.job.isRunning():
            self.message.setText("The current check is finishing. No runtime has been started.")
            event.ignore()
        else:
            event.accept()


def default_setup_root(role):
    if os.name == "nt":
        parent = os.environ.get("LOCALAPPDATA")
        if not parent:
            raise SettingsError("SETTINGS_PATH_INVALID")
        return Path(parent) / ("TB4-R2-" + role)
    return Path.home() / (".tb4-r2-" + role)


class SetupStart(QtWidgets.QWidget):
    """No filesystem mutation until owner selects Create/Open in this local UI."""
    def __init__(self, role, root, *, controller_factory=open_setup):
        super().__init__()
        self.role,self.root,self.factory,self.opened = role,root,controller_factory,None
        self.setWindowTitle("TB4 " + role.upper() + " — private setup")
        self.resize(650,260)
        layout=QtWidgets.QVBoxLayout(self)
        layout.addWidget(plain_label("Choose the private local location for this installation's setup. Existing settings and permissions are never reset."))
        self.location=plain_label(str(root))
        layout.addWidget(self.location)
        self.select=QtWidgets.QPushButton("Choose another private folder")
        self.select.clicked.connect(self.choose_parent)
        layout.addWidget(self.select)
        self.open=QtWidgets.QPushButton("Create or open setup")
        self.open.clicked.connect(self.open_selected)
        layout.addWidget(self.open)
        self.message=plain_label("")
        layout.addWidget(self.message)

    def choose_parent(self):
        selected=QtWidgets.QFileDialog.getExistingDirectory(self,"Choose a private parent folder")
        if selected:
            self.root=Path(selected)/("TB4-R2-"+self.role)
            self.location.setText(str(self.root))

    def open_selected(self):
        try:
            controller=self.factory(self.root,role=self.role,create=not self.root.exists())
            self.opened=SetupWindow(controller)
            self.opened.show()
            self.hide()
        except Exception:
            self.message.setText("This location could not be verified. Select a private local folder; existing permissions were not changed.")


def run_setup(role, *, root=None, smoke_report=None, smoke=False, installation_root=None):
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setApplicationName("TB4 " + role.upper() + " setup")
    temporary=None
    try:
        if smoke:
            temporary=tempfile.TemporaryDirectory(prefix="tb4-setup-ui-smoke-")
            root=Path(temporary.name)/"uncreated-settings"
        root=root or default_setup_root(role)
        start=SetupStart(role,root,controller_factory=lambda chosen,**options:
                         open_setup(chosen,installation_root=installation_root,**options))
        start.show()
        if smoke:
            def finish():
                report=dict(role=role,setup_gui_smoke="PASS" if start.isVisible()
                    and start.open.isEnabled() and not root.exists() else "FAIL",
                    settings_created=root.exists(),runtime_started=False)
                if smoke_report:
                    smoke_report.write_text(json.dumps(report),encoding="utf-8")
                start.close()
                app.quit()
            QtCore.QTimer.singleShot(200,finish)
        return app.exec()
    finally:
        if temporary is not None:
            temporary.cleanup()
