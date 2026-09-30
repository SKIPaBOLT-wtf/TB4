from __future__ import annotations

import base64
import io
import json
import sys
from urllib.parse import quote

import pytest

from tb4.privacy import (PrivacyError, classify_field, exception_code, private_projection,
                         public_artifact, public_diagnostic)
from tb4.desktop.telemetry import Telemetry, append_event, decode_snapshot, diagnostic_report
from tb4.desktop.worker import SnapshotEmitter
from tb4.desktop.process import WorkerProcess
from tests.desktop.test_process import wait_exit

CANARY = "CANARY_PRIVATE_VALUE_" + "K" * 16
VARIANTS = [CANARY, base64.b64encode(CANARY.encode()).decode(), CANARY.encode().hex(),
            "https://example.invalid/path?secret=" + quote(CANARY), "%" + "%".join(f"{ord(c):02X}" for c in CANARY)]


@pytest.mark.parametrize("field", ["password", "access_token", "refresh_token", "client_secret", "private_key"])
def test_secret_values_are_local_only(field):
    assert classify_field(field) == "LOCAL_SECRET"


@pytest.mark.parametrize("field", ["path", "credential_ref", "root_id", "device_id", "address", "hostname", "new_field"])
def test_real_bindings_and_unknown_fields_default_protected(field):
    assert classify_field(field) == "PROTECTED"


@pytest.mark.parametrize("canary", VARIANTS)
def test_arbitrary_nested_or_code_shaped_values_never_reach_public_report(canary):
    raw = {name: canary for name in ("stage", "last_outcome", "error_code", "protocol_state", "process_state")}
    raw.update(config={"nested": [canary]}, exception=RuntimeError(canary), filename=canary + ".png")
    report = public_diagnostic("fetcher", raw, canary)
    filename, body = public_artifact("diagnostic", report)
    assert canary not in body.decode() + filename
    assert report["remote_observation"] == "UNKNOWN"
    assert "config" not in report and "exception" not in report


@pytest.mark.parametrize("field", ["stage", "last_outcome", "error_code", "protocol_state"])
def test_uppercase_canary_is_not_a_safe_worker_code(field):
    snapshot = Telemetry("fetcher", lambda: 100.).snapshot()
    snapshot[field] = CANARY if field != "protocol_state" else "DOG_" + CANARY
    with pytest.raises(ValueError) as error:
        decode_snapshot(json.dumps(snapshot).encode(), "fetcher")
    assert CANARY not in str(error.value)


def test_emitter_rejects_custom_error_names_and_messages():
    Error = type(CANARY, (Exception,), {})
    assert exception_code(Error(CANARY)) == "UNCLASSIFIED_ERROR"
    t = Telemetry("fetcher", lambda: 100.)
    t.fail(CANARY)
    t.record("read_text", CANARY)
    stream = io.StringIO()
    SnapshotEmitter(t, stream).emit()
    assert CANARY not in stream.getvalue()
    result = json.loads(stream.getvalue())
    assert result["error_code"] == "UNCLASSIFIED_ERROR" and result["last_outcome"] == "UNKNOWN"


def test_private_log_boundary_does_not_trust_extra_dictionary_fields(tmp_path):
    snapshot = Telemetry("fetcher", lambda: 100.).snapshot()
    snapshot.update(raw_provider={"nested": VARIANTS}, stdout=CANARY, environment={"private": CANARY})
    path = tmp_path / "events.jsonl"
    append_event(path, snapshot)
    body = path.read_text()
    assert not any(value in body for value in VARIANTS)
    snapshot["stage"] = CANARY
    with pytest.raises(ValueError, match="LOG_SNAPSHOT_INVALID"):
        append_event(path, snapshot)
    assert path.read_text() == body


def test_public_export_removes_activity_times_and_uses_fixed_filename():
    snapshot = Telemetry("fetcher", lambda: 100.).snapshot()
    snapshot["filename"] = CANARY + ".json"
    report = diagnostic_report("fetcher", snapshot, 100.)
    name, body = public_artifact("diagnostic", report)
    assert name == "tb4-fetcher-diagnostics.json"
    assert report["schema_version"] == 2
    assert all(key not in body.decode() for key in ("observed_at", "generated_at", "last_drive_at", CANARY))


@pytest.mark.parametrize("kind", ["screenshot", "png", "raw-log", "stdout", "stderr", "config", "private-projection"])
def test_pixels_binary_and_raw_exports_are_not_automatically_public(kind):
    with pytest.raises(PrivacyError, match="ARTIFACT_REQUIRES_PRIVATE_REVIEW") as error:
        public_artifact(kind, {"filename": CANARY + ".png", "pixels": CANARY.encode()})
    assert CANARY not in str(error.value)


def test_tampered_report_and_private_projection_cannot_use_public_export():
    report = public_diagnostic("watchdog", {}, "UNKNOWN")
    report["raw"] = CANARY
    with pytest.raises(PrivacyError, match="PUBLIC_REPORT_INVALID"):
        public_artifact("diagnostic", report)
    projection = private_projection({"devices": [{"alias": "target-a", "role": "fetcher"}]})
    with pytest.raises(PrivacyError, match="PUBLIC_REPORT_INVALID"):
        public_artifact("diagnostic", projection)


def test_private_projection_omits_all_raw_bindings_and_credentials():
    projection = private_projection({"devices": [dict(alias="target-a", role="fetcher", host=CANARY,
        password=CANARY, credential_ref=CANARY, path=CANARY, root_id=CANARY,
        capabilities={"ssh_status": True, "ssh_start": False, "raw": CANARY})]})
    assert CANARY not in json.dumps(projection)
    assert projection["devices"][0]["capabilities"] == dict(ssh_status=True, ssh_start=False, wake=False)
    for field in ("alias", "role", "capabilities"):
        with pytest.raises(PrivacyError, match="PRIVATE_PROJECTION_INVALID") as error:
            private_projection({"devices": [{"alias": "target-a", "role": "fetcher", field: CANARY}]})
        assert CANARY not in str(error.value)


def test_stdout_stderr_canaries_never_enter_parent_events():
    snapshot = Telemetry("watchdog", lambda: 100.).snapshot()
    snapshot["error_code"] = CANARY
    program = "import sys\nprint(" + repr(json.dumps(snapshot)) + ")\nprint(" + repr(VARIANTS[1]) + ",file=sys.stderr)\n"
    client = WorkerProcess("watchdog")
    client.start([sys.executable, "-c", program], "check")
    events = wait_exit(client)
    text = json.dumps(events)
    assert CANARY not in text and VARIANTS[1] not in text
    assert "WORKER_OUTPUT_INVALID" in text and "WORKER_STDERR_REDACTED" in text
