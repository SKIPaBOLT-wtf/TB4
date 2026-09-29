import json
from types import SimpleNamespace

import pytest

from tb4.desktop.telemetry import (
    ObservedBackend, Telemetry, append_event, decode_snapshot,
    diagnostic_report, observation_state,
)


def test_observer_adds_no_backend_calls_and_does_not_claim_mutation_readback():
    calls = []
    class Backend:
        capabilities = 'unchanged'
        def get_metadata(self, object_id):
            calls.append(('get', object_id))
            return SimpleNamespace(ok=True, outcome=SimpleNamespace(value='OK'), value=SimpleNamespace(name='FETCH_BALL_READY'))
        def rename(self, object_id, new_name, **kwargs):
            calls.append(('rename', object_id, new_name, kwargs))
            return SimpleNamespace(ok=True, outcome=SimpleNamespace(value='OK'), value=SimpleNamespace(name=new_name))
    t = Telemetry('fetcher', lambda: 100., protocol_names=frozenset({'FETCH_BALL_READY'}))
    b = ObservedBackend(Backend(), t)
    assert b.capabilities == 'unchanged'
    b.get_metadata('secret-id')
    b.rename('secret-id', 'FETCH_BALL_CHEW', expected_version_token='private-version')
    assert len(calls) == 2
    assert t.snapshot()['protocol_state'] == 'FETCH_BALL_READY'
    assert 'secret-id' not in json.dumps(t.snapshot())
    assert 'private-version' not in json.dumps(t.snapshot())


def test_event_history_and_unknown_names_are_bounded():
    t = Telemetry('watchdog', lambda: 100.)
    for i in range(1000):
        t.record('get_metadata', 'OK', 'DOG_PRIVATE_SECRET')
    assert len(t.events) == 100
    assert t.snapshot()['protocol_state'] is None


def test_unknown_recent_stale_and_clock_uncertain():
    t = Telemetry('fetcher', lambda: 100.)
    assert observation_state(t.snapshot(), 100.) == 'UNKNOWN'
    t.record('read_text', 'OK')
    assert observation_state(t.snapshot(), 100.) == 'RECENT_RESPONSE'
    assert observation_state(t.snapshot(), 120.) == 'STALE'
    assert observation_state(t.snapshot(), 80.) == 'CLOCK_UNCERTAIN'


def test_diagnostics_strip_all_unapproved_fields():
    s = Telemetry('watchdog', lambda: 100.).snapshot()
    s.update({'token': 'PRIVATE_TOKEN', 'payload': 'PRIVATE_COMMAND', 'path': '/private/config'})
    report = diagnostic_report('watchdog', s, 100.)
    encoded = json.dumps(report)
    assert all(value not in encoded for value in ('PRIVATE_TOKEN', 'PRIVATE_COMMAND', '/private/config'))


@pytest.mark.parametrize('mutation', [
    {'role': 'watchdog'}, {'process_state': 'PASSWORD'}, {'observed_at': float('nan')},
    {'observed_at': True}, {'last_operation': 'run-private-command'},
    {'last_outcome': 'token contains secret'}, {'protocol_state': 'private file'},
])
def test_bad_worker_messages_rejected(mutation):
    s = Telemetry('fetcher', lambda: 100.).snapshot()
    s.update(mutation)
    with pytest.raises(ValueError):
        decode_snapshot(json.dumps(s).encode(), 'fetcher')


def test_bad_json_and_oversized_messages():
    for line in (b'not json', b'[]', b'x' * 9000):
        with pytest.raises(ValueError):
            decode_snapshot(line, 'fetcher')


def test_rotated_logs_remain_bounded(tmp_path):
    path = tmp_path / 'events.jsonl'
    snapshot = Telemetry('fetcher', lambda: 100.).snapshot()
    for _ in range(40):
        append_event(path, snapshot, max_bytes=1000)
    assert path.stat().st_size < 1000
    assert path.with_suffix('.previous.jsonl').stat().st_size < 1000
    assert len(list(tmp_path.iterdir())) == 2


def test_exceptions_record_only_classification():
    class Backend:
        def read_text(self, object_id):
            raise RuntimeError('private provider body')
    t = Telemetry('fetcher', lambda: 100.)
    with pytest.raises(RuntimeError):
        ObservedBackend(Backend(), t).read_text('secret')
    assert t.snapshot()['last_outcome'] == 'EXCEPTION'
    assert 'private provider' not in json.dumps(t.snapshot())
