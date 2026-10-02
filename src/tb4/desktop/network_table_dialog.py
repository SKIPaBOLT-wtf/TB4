"""Owner-local network settings/description editor; no router or shared writes."""
from pathlib import Path
import time

from PySide6 import QtCore, QtWidgets

from tb4.network_table import DEVICE_KINDS, CAPABILITIES, draft
from .setup_app import plain_label

ERROR = "The change could not be verified. Previous data and the pending change were preserved."


class NetworkTableDialog(QtWidgets.QDialog):
    def __init__(self, table, parent=None):
        super().__init__(parent)
        self.table, self._proposal = table, None
        self.setWindowTitle("TB4 — network devices")
        self.resize(650, 650)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(plain_label("TB4 checks the network and reports devices needing a description. Network settings are managed by their owner."))
        self.location = QtWidgets.QLineEdit()
        self.location.setMaxLength(4096)
        try:
            self.location.setText(table.local_location())
        except Exception:
            self.location.setPlaceholderText("Choose a private local location")
        self.choose = QtWidgets.QPushButton("Choose another table location")
        self.choose.clicked.connect(self.choose_location)
        self.save_location = QtWidgets.QPushButton("Save table location")
        self.save_location.clicked.connect(self.change_location)
        form = QtWidgets.QFormLayout()
        form.addRow("Private table folder", self.location)
        layout.addLayout(form)
        layout.addWidget(self.choose)
        layout.addWidget(self.save_location)
        self.devices = QtWidgets.QComboBox()
        self.devices.currentIndexChanged.connect(self.select_device)
        form.addRow("Device", self.devices)
        self.kind = self.combo(DEVICE_KINDS)
        self.os = self.combo(("UNKNOWN", "WINDOWS", "LINUX", "OTHER"))
        self.arch = self.combo(("UNKNOWN", "X64", "ARM64", "X86", "OTHER"))
        form.addRow("Device type", self.kind)
        form.addRow("Operating system", self.os)
        form.addRow("Architecture", self.arch)
        self.roles, self.launch = {}, {}
        for role in ("watchdog", "fetcher"):
            self.roles[role] = QtWidgets.QCheckBox("This device can host " + role.upper())
            self.launch[role] = self.combo(("UNSUPPORTED", "DESKTOP_SESSION", "OS_SERVICE", "EXTERNAL"))
            form.addRow("", self.roles[role])
            form.addRow(role.upper() + " start method", self.launch[role])
        self.transports = {k: QtWidgets.QCheckBox(k) for k in ("DRIVE_API", "SHARED_FOLDER", "SSH", "WOL")}
        for box in self.transports.values():
            form.addRow("Connection", box)
        self.capabilities = {k: self.combo(("UNKNOWN", "SUPPORTED", "UNSUPPORTED")) for k in CAPABILITIES}
        for key, box in self.capabilities.items():
            form.addRow(key.replace("_", " ").capitalize(), box)
        self.stable_ip = QtWidgets.QComboBox()
        for label, value in (("Unknown", "UNKNOWN"), ("Owner reports assigned", "ASSIGNED"),
                             ("Owner reports not assigned", "NOT_ASSIGNED")):
            self.stable_ip.addItem(label, value)
        form.addRow("Stable IP status", self.stable_ip)
        layout.addWidget(plain_label("A stable IP is optional. These descriptions do not register FETCHER or grant permission to run work."))
        self.approve = QtWidgets.QPushButton("Approve this device description")
        self.approve.clicked.connect(self.approve_description)
        layout.addWidget(self.approve)
        self.inspect = QtWidgets.QPushButton("Inspect pending table change")
        self.inspect.clicked.connect(self.inspect_change)
        self.complete = QtWidgets.QPushButton("Complete the same local change")
        self.complete.clicked.connect(self.complete_change)
        layout.addWidget(self.inspect)
        layout.addWidget(self.complete)
        self.message = plain_label("")
        layout.addWidget(self.message)
        self.refresh()

    @staticmethod
    def combo(values):
        box = QtWidgets.QComboBox()
        for value in values:
            box.addItem(value.replace("_", " ").capitalize(), value)
        return box

    def choose_location(self):
        selected = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose a private parent folder")
        if selected:
            self.location.setText(str(Path(selected) / "network-table"))

    def refresh(self):
        self._proposal = None
        old_id = self.devices.currentData()
        self.devices.blockSignals(True)
        self.devices.clear()
        try:
            status = self.table.status(now=int(time.time()))
            for row in status["devices"]:
                self.devices.addItem(row["alias"] + " — " + row["description_status"].replace("_", " ").lower(),
                                     row["device_id"])
            self.devices.setCurrentIndex(max(0, self.devices.findData(old_id)))
            pending = status["maintenance"] != "NONE"
            self.inspect.setEnabled(pending)
            self.complete.setEnabled(pending)
            self.save_location.setEnabled(not pending)
            self.message.setText(str(status["needs_description"]) + " devices need a current description.")
        except Exception:
            pending = self.table.setup._payload.get("network_table", {}).get("pending") is not None
            self.inspect.setEnabled(pending)
            self.complete.setEnabled(pending)
            self.save_location.setEnabled(not pending)
            self.message.setText("Create the local table after storage identity and discovery are configured."
                                 if self.table.setup._payload.get("network_table") is None else ERROR)
        finally:
            self.devices.blockSignals(False)
        self.select_device()
        self.approve.setEnabled(self._proposal is not None and not pending)

    def select_device(self):
        self._proposal = None
        device_id = self.devices.currentData()
        if device_id is None:
            self.approve.setEnabled(False)
            return
        try:
            self._proposal = draft(self.table.read(), device_id)
            body = self._proposal["description"]
            for box, value in ((self.kind, body["device_kind"]), (self.os, body["platform"]["os"]),
                               (self.arch, body["platform"]["architecture"]), (self.stable_ip, body["stable_ip"])):
                box.setCurrentIndex(box.findData(value))
            for role in self.roles:
                self.roles[role].setChecked(role in body["roles"])
                self.launch[role].setCurrentIndex(self.launch[role].findData(body["launch_mode"].get(role, "UNSUPPORTED")))
            for key, box in self.transports.items():
                box.setChecked(key in body["transports"])
            for key, box in self.capabilities.items():
                box.setCurrentIndex(box.findData(body["capabilities"][key]))
            self.approve.setEnabled(True)
        except Exception:
            self.approve.setEnabled(False)
            self.message.setText(ERROR)

    def change_location(self):
        try:
            if self.table.setup._payload.get("network_table") is None:
                self.table.configure(Path(self.location.text()), owner_authorized=True)
            else:
                self.table.move(Path(self.location.text()), owner_authorized=True)
            self.refresh()
        except Exception:
            self.refresh()
            self.message.setText(ERROR)

    def approve_description(self):
        if self._proposal is None:
            return
        body = dict(device_kind=self.kind.currentData(),
                    platform=dict(os=self.os.currentData(), architecture=self.arch.currentData()),
                    roles=[role for role, box in self.roles.items() if box.isChecked()],
                    launch_mode={role:self.launch[role].currentData() for role,box in self.roles.items() if box.isChecked()},
                    transports=[key for key,box in self.transports.items() if box.isChecked()],
                    capabilities={key:box.currentData() for key,box in self.capabilities.items()},
                    stable_ip=self.stable_ip.currentData())
        try:
            self.table.approve({**self._proposal, "description":body}, now=int(time.time()), owner_authorized=True)
            self.refresh()
        except Exception:
            self.message.setText(ERROR)

    def inspect_change(self):
        try:
            self.table.inspect()
            self.refresh()
        except Exception:
            self.message.setText(ERROR)

    def complete_change(self):
        try:
            self.table.resume(owner_authorized=True)
            self.refresh()
        except Exception:
            self.message.setText(ERROR)
