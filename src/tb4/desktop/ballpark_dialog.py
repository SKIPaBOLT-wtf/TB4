"""Local owner review; provider operations stay outside the Qt event thread."""
import copy

from PySide6 import QtCore, QtWidgets

from tb4.ballpark_records import SYSTEMS, ARCH, LAUNCH, TRANSPORTS
from .setup_app import plain_label


def combo(values, selected):
    widget = QtWidgets.QComboBox()
    for value in values:
        widget.addItem(value.replace("_", " ").title(), value)
    widget.setCurrentIndex(widget.findData(selected))
    return widget


class Job(QtCore.QThread):
    result = QtCore.Signal(dict)
    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action
    def run(self):
        try:
            self.result.emit(self.action())
        except Exception:
            self.result.emit({"error": True})


class BallparkDialog(QtWidgets.QDialog):
    def __init__(self, publisher, parent=None):
        super().__init__(parent)
        self.publisher, self.job, self.rows, self.snapshot = publisher, None, [], None
        self.setWindowTitle("TB4 — review environment")
        self.resize(660, 600)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(plain_label("Choose which known devices belong in this environment. These choices do not grant access or prove that a device is ready."))
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll)
        self.topology = combo(("", "FLAT", "ROUTED", "MULTI_SUBNET", "VPN", "ISOLATED", "MIXED"), "")
        self.topology.setItemText(0, "Choose the local network arrangement")
        layout.addWidget(self.topology)
        self.message = plain_label("Load compatible guidance to review the saved choices.")
        layout.addWidget(self.message)
        self.prepare = QtWidgets.QPushButton("Load choices")
        self.confirm = QtWidgets.QPushButton("Approve this draft")
        self.publish = QtWidgets.QPushButton("Publish approved draft")
        self.inspect = QtWidgets.QPushButton("Check earlier publication")
        for button in (self.prepare, self.confirm, self.publish, self.inspect): layout.addWidget(button)
        self.prepare.clicked.connect(lambda: self.start(self.load))
        self.confirm.clicked.connect(self.approve)
        self.publish.clicked.connect(lambda: self.start(self.publish_approved))
        self.inspect.clicked.connect(lambda: self.start(lambda: self.perform(self.publisher.inspect)))
        self.render(self.state())

    def state(self):
        p = self.publisher
        saved = p._state()
        draft = p.setup._payload.get("ballpark_draft")
        return dict(pending=saved["pending"] is not None, active=saved["active"] is not None,
            draft=copy.deepcopy(draft["proposal"]) if draft else None,
            approved=draft is not None and draft["candidate"] is not None,
            topology=draft["candidate"]["topology"] if draft and draft["candidate"] else "",
            targets=[] if draft is None or saved["pending"] is not None else p.guide.questions()["targets"])

    def load(self):
        self.publisher.guide.begin()
        return self.state()

    def perform(self, action):
        outcome = action()
        return {**self.state(), "outcome": outcome}

    def publish_approved(self):
        if self.publisher.guide.pin is None:
            self.publisher.guide.begin()  # Restore the same closure after restart.
        return self.perform(self.publisher.publish)

    def approve(self):
        if not self.snapshot or not self.snapshot["draft"] or self.job is not None:
            return
        devices = []
        for device_id, selected, roles, system, architecture, launch, transports in self.rows:
            if selected.isChecked():
                chosen = [r for r,w in roles.items() if w.isChecked()]
                devices.append(dict(device_id=device_id, roles=chosen,
                    platform=dict(os=system.currentData(), architecture=architecture.currentData()),
                    launch_mode={r: launch[r].currentData() for r in chosen},
                    transports=[t for t,w in transports.items() if w.isChecked()]))
        proposal = dict(schema_version=1, expected_revision=self.snapshot["draft"]["expected_revision"], devices=devices)
        topology = self.topology.currentData()
        def action():
            self.publisher.guide.propose(proposal)
            sample = self.publisher.discovery.clock()
            self.publisher.guide.confirm(topology=topology, at=sample.utc, owner_authorized=True)
            return self.state()
        self.start(action)

    def start(self, action):
        if self.job is not None: return
        self.job = Job(action, self)
        for widget in (self.scroll, self.topology, self.prepare, self.confirm, self.publish, self.inspect):
            widget.setEnabled(False)
        self.message.setText("Checking the selected environment…")
        self.job.result.connect(self.render)
        self.job.finished.connect(self.job_finished)
        self.job.start()

    def render(self, value):
        if value.get("error"):
            self.message.setText("The change could not be verified. Saved choices are preserved; an uncertain publication can only be checked.")
            try: self.snapshot = self.state()
            except Exception: self.snapshot = None
            return
        self.snapshot = value
        self.rows = []
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        choices = {d["device_id"]:d for d in (value["draft"] or {}).get("devices", [])}
        for target in value["targets"]:
            row = choices.get(target["device_id"], {})
            selected = QtWidgets.QCheckBox(target["alias"])
            selected.setChecked(bool(row))
            layout.addWidget(selected)
            form = QtWidgets.QFormLayout()
            roles, launch, transports = {}, {}, {}
            for role in ("watchdog", "fetcher"):
                roles[role] = QtWidgets.QCheckBox(role.upper())
                roles[role].setChecked(role in row.get("roles", []))
                launch[role] = combo(LAUNCH, row.get("launch_mode", {}).get(role, "UNSUPPORTED"))
                form.addRow(roles[role], launch[role])
            platform = row.get("platform", {})
            system, architecture = combo(SYSTEMS, platform.get("os", "UNKNOWN")), combo(ARCH, platform.get("architecture", "UNKNOWN"))
            form.addRow("Operating system", system)
            form.addRow("Architecture", architecture)
            for transport in TRANSPORTS:
                transports[transport] = QtWidgets.QCheckBox(transport.replace("_", " "))
                transports[transport].setChecked(transport in row.get("transports", []))
                form.addRow("Connection option", transports[transport])
            layout.addLayout(form)
            self.rows.append((target["device_id"], selected, roles, system, architecture, launch, transports))
        if not value["targets"]: layout.addWidget(plain_label("No editable device choices are available. Existing publications are preserved."))
        self.scroll.setWidget(content)
        self.topology.setCurrentIndex(self.topology.findData(value["topology"]))
        self.message.setText("An earlier publication needs checking; it will not be repeated." if value["pending"] else
            "The draft is approved and ready to publish." if value["approved"] else
            "The environment is published. Load choices to prepare a new revision." if value["active"] and not value["draft"] else
            "Review the choices and select the local network arrangement before approving.")
        self.buttons()

    def buttons(self):
        value = self.snapshot
        idle = self.job is None and value is not None
        editable = idle and not value["pending"] and not value["approved"]
        self.prepare.setEnabled(editable)
        self.confirm.setEnabled(editable and bool(value["targets"]))
        self.publish.setEnabled(idle and value["approved"] and not value["pending"])
        self.inspect.setEnabled(idle and value["pending"])
        self.scroll.setEnabled(editable)
        self.topology.setEnabled(editable)

    def job_finished(self):
        job, self.job = self.job, None
        job.deleteLater()
        self.buttons()

    def reject(self):
        if self.job is None: super().reject()

    def closeEvent(self, event):
        if self.job is not None: event.ignore()
        else: event.accept()
