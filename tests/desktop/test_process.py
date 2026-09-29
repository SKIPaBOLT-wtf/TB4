import json
import sys
import time

import pytest

from tb4.desktop.process import WorkerProcess, worker_command
from tb4.desktop.profile import profile_for
from tb4.desktop.telemetry import Telemetry


def wait_exit(client, timeout=5):
    events = []
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        event = client.events.get(timeout=max(.01, end - time.monotonic()))
        events.append(event)
        if event['kind'] == 'exit':
            return events
    raise AssertionError('worker exit was not observed')


def test_worker_command_uses_argv_and_role_specific_profile(tmp_path):
    p = profile_for('fetcher', tmp_path / 'space in path')
    command = worker_command(p, 'check')
    assert command[-1] == str(p.directory.parent)
    assert command[-3:-1] == ['check', '--profile-root']
    assert '--role' in command and 'fetcher' in command


def test_stop_is_a_cooperative_pipe_message_not_a_kill():
    client = WorkerProcess('fetcher')
    snapshot = Telemetry('fetcher', lambda: 100.).snapshot()
    program = ('import json, sys\n'
               f'print({json.dumps(json.dumps(snapshot))}, flush=True)\n'
               'message=json.loads(sys.stdin.readline())\n'
               'sys.exit(0 if message == {"op":"stop"} else 7)\n')
    client.start([sys.executable, '-c', program], 'run')
    with pytest.raises(RuntimeError, match='ALREADY_RUNNING'):
        client.start([sys.executable, '-c', 'pass'], 'run')
    assert client.request_stop()
    events = wait_exit(client)
    assert any(e['kind'] == 'snapshot' for e in events)
    assert events[-1]['code'] == 0
    assert not client.active
    assert not client.request_stop()


def test_bad_stdout_and_stderr_never_enter_event_content():
    client = WorkerProcess('watchdog')
    program = 'import sys; print("secret token payload"); print("private config", file=sys.stderr)'
    client.start([sys.executable, '-c', program], 'check')
    events = wait_exit(client)
    text = json.dumps(events)
    assert 'secret token payload' not in text
    assert 'private config' not in text
    assert 'WORKER_OUTPUT_INVALID' in text and 'WORKER_STDERR_REDACTED' in text


def test_large_configuration_payload_reaches_worker_without_ui_wait():
    client = WorkerProcess('fetcher')
    payload = {'text': 'x' * 220000, 'expected_digest': None}
    program = 'import json,sys; p=json.loads(sys.stdin.readline()); sys.exit(0 if len(p["text"])==220000 else 9)'
    before = time.monotonic()
    client.start([sys.executable, '-c', program], 'save', payload)
    assert time.monotonic() - before < 2
    assert wait_exit(client)[-1]['code'] == 0


def test_queue_is_bounded():
    client = WorkerProcess('fetcher')
    for number in range(1000):
        client._event({'kind': 'sample', 'number': number})
    assert client.events.qsize() == 200
