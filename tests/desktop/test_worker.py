import io
import json
import threading

from tb4.desktop import worker
from tb4.desktop.profile import profile_for
from tb4.desktop.telemetry import Telemetry


def test_control_stop_and_parent_eof():
    for content in ('{"op":"stop"}\n', '', 'not-json\n', 'x' * 2048):
        stop = threading.Event()
        worker._listen(io.StringIO(content), stop)
        assert stop.is_set()


def test_snapshot_emitter_does_not_include_private_provider_text():
    stream = io.StringIO()
    t = Telemetry('fetcher', lambda: 100.)
    t.fail('PRIVATE content is not an allowed error code')
    worker.SnapshotEmitter(t, stream).emit()
    value = json.loads(stream.getvalue())
    assert value['error_code'] == 'UNCLASSIFIED_ERROR'
    assert 'PRIVATE content' not in stream.getvalue()


def test_worker_failure_reports_stage_and_class_without_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(worker, 'canonical_protocol_names', lambda: frozenset())
    def fail(*args):
        args[2].set_state('STARTING', 'ROOT_AND_MAP')
        raise RuntimeError('do not export my root ID or token')
    monkeypatch.setattr(worker, 'run_action', fail)
    assert worker.main(profile_for('fetcher', tmp_path), 'save') == 1
    output = capsys.readouterr().out
    assert 'do not export' not in output
    snapshots = [json.loads(line) for line in output.splitlines()]
    assert snapshots[-1]['process_state'] == 'FAILED'
    assert snapshots[-1]['stage'] == 'ROOT_AND_MAP'
    assert snapshots[-1]['error_code'] == 'ERROR_RUNTIMEERROR'


def test_worker_success_emits_terminal_snapshot(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(worker, 'canonical_protocol_names', lambda: frozenset())
    monkeypatch.setattr(worker, 'run_action', lambda *args: 0)
    assert worker.main(profile_for('watchdog', tmp_path), 'save') == 0
    snapshots = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert snapshots[-1]['process_state'] == 'EXITED'
