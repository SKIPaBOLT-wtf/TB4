from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tb4.core.retry import RetryPolicy
from tb4.core.schemas import canonical_json_text
from tb4.drive.bootstrap import bootstrap_tree
from tb4.drive.device_registration import DeviceProfile, DeviceRegistrar
from tb4.drive.errors import BackendOutcome
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.fetcher.return_recovery import ReturnRecoveryError, recover_returning
from tb4.runtime_support import RuntimeContext, load_public_defaults


NOW = 1_700_000_500
FIXTURE = Path(__file__).resolve().parents[2] / 'protocol/examples/fetch-ball/inline-toss.json'


def setup_case(result_code='CANCELLED'):
    backend = InMemoryDriveBackend()
    boot = bootstrap_tree(backend, root_id=backend.root_id)
    park = DeviceRegistrar(backend).register(
        boot.park_map,
        DeviceProfile('pilot-target', 'pilot-target', None, 'WINDOWS', False, False),
    ).park_map
    ball_id = park.lookup_device('pilot-target', 'PLAYGROUND.FETCH_BALL')
    pulse_id = park.lookup_device('pilot-target', 'DOG_PULSE')
    body = json.loads(FIXTURE.read_text(encoding='utf-8'))
    body.update(
        started_at=1_700_000_001,
        finished_at=1_700_000_040,
        result_code=result_code,
        reason_code='RECORDED_TEST_RESULT',
        exit_code=0 if result_code == 'DONE' else None,
        effects_known='KNOWN' if result_code == 'DONE' else 'NONE',
        stdout_tail='output already produced before shutdown\n',
        stderr_tail='',
    )
    body['payload_sha256'] = hashlib.sha256(body['inline_payload'].encode()).hexdigest()
    body['result_sha256'] = hashlib.sha256(canonical_json_text(body).encode()).hexdigest()
    text = canonical_json_text(body)
    assert backend.rename(ball_id, 'FETCH_BALL_RETURNING').ok
    assert backend.replace_text(ball_id, text).ok
    pulse = {
        'schema_version': 1, 'protocol_major': 1, 'device_id': 'pilot-target',
        'instance_id': 'previous-instance', 'sequence': 1, 'emitted_at': 1_700_000_050,
        'claimed_generation': body['generation'], 'claimed_operation_id': body['operation_id'],
    }
    assert backend.replace_text(pulse_id, canonical_json_text(pulse)).ok
    archived = backend.create_text(park.lookup_device('pilot-target', 'BONEYARD'), 'before-recovery.json', text)
    assert archived.ok and archived.value is not None
    ticket = {
        'operation_id': body['operation_id'], 'generation': body['generation'],
        'result_sha256': body['result_sha256'], 'archive_id': archived.value.metadata.object_id,
        'reviewed': True,
    }
    context = RuntimeContext(
        {'identity': {'device_id': 'pilot-target'}}, load_public_defaults(), backend,
        park, RetryPolicy((0.01, 0.02), 2),
    )
    backend.reset_operation_counts()
    return context, ticket, body, ball_id, pulse_id


def recover(context, ticket):
    return recover_returning(context, ticket, now_epoch_s=NOW, sleeper=lambda _: None)


@pytest.mark.parametrize('result_code', ['DONE', 'FAILED', 'CANCELLED'])
def test_explicit_recovery_preserves_body_and_never_executes(monkeypatch, result_code):
    context, ticket, body, ball, _ = setup_case(result_code)
    before = context.backend.read_text(ball).value.text

    def no_process(*args, **kwargs):
        raise AssertionError('recovery must never execute a payload')

    monkeypatch.setattr(subprocess, 'Popen', no_process)
    assert recover(context, ticket) == 'FETCH_BALL_' + result_code
    assert context.backend.read_text(ball).value.text == before
    assert context.backend.operation_counts.get('replace_text', 0) == 0
    assert context.backend.operation_counts.get('rename', 0) == 1
    assert context.backend.operation_counts.get('list_children', 0) == 0
    stop = context.park_map.lookup_device('pilot-target', 'PLAYGROUND.STOP_BALL')
    assert context.backend.get_metadata(stop).value.name == 'STOP_BALL_READY'
    # Publication preserves a recorded classification, not proof of early cancellation.
    assert json.loads(before)['stdout_tail'] == body['stdout_tail']


@pytest.mark.parametrize('field,value', [('reviewed', False), ('generation', True), ('generation', 8), ('operation_id', 'different-operation'), ('result_sha256', '0' * 64)])
def test_unreviewed_or_mismatched_ticket_cannot_mutate(field, value):
    context, ticket, _, ball, _ = setup_case()
    ticket[field] = value
    with pytest.raises(ReturnRecoveryError):
        recover(context, ticket)
    assert context.backend.get_metadata(ball).value.name == 'FETCH_BALL_RETURNING'
    assert context.backend.operation_counts.get('rename', 0) == 0


@pytest.mark.parametrize('state', ['CHEW', 'TOSS', 'READY', 'GONE'])
def test_recovery_never_takes_other_lifecycle_states(state):
    context, ticket, _, ball, _ = setup_case()
    assert context.backend.rename(ball, 'FETCH_BALL_' + state).ok
    context.backend.reset_operation_counts()
    with pytest.raises(ReturnRecoveryError):
        recover(context, ticket)
    assert context.backend.operation_counts.get('rename', 0) == 0


def test_fresh_fetcher_pulse_blocks_takeover():
    context, ticket, _, ball, pulse_id = setup_case()
    pulse = json.loads(context.backend.read_text(pulse_id).value.text)
    pulse['emitted_at'] = NOW - 1
    assert context.backend.replace_text(pulse_id, canonical_json_text(pulse)).ok
    context.backend.reset_operation_counts()
    with pytest.raises(ReturnRecoveryError, match='PULSE'):
        recover(context, ticket)
    assert context.backend.operation_counts.get('rename', 0) == 0


@pytest.mark.parametrize('archive_change', ['body', 'parent', 'live_alias'])
def test_verified_separate_archive_is_required(archive_change):
    context, ticket, _, ball, _ = setup_case()
    if archive_change == 'body':
        assert context.backend.replace_text(ticket['archive_id'], '{}').ok
    elif archive_change == 'parent':
        assert context.backend.move(ticket['archive_id'], context.park_map.root_id).ok
    else:
        ticket['archive_id'] = ball
    context.backend.reset_operation_counts()
    with pytest.raises(ReturnRecoveryError):
        recover(context, ticket)
    assert context.backend.operation_counts.get('rename', 0) == 0


def test_tampered_live_body_is_not_hidden_by_matching_hash_field():
    context, ticket, body, ball, _ = setup_case()
    body['stdout_tail'] = 'tampered'
    assert context.backend.replace_text(ball, canonical_json_text(body)).ok
    context.backend.reset_operation_counts()
    with pytest.raises(ReturnRecoveryError):
        recover(context, ticket)
    assert context.backend.operation_counts.get('rename', 0) == 0


def test_repeating_same_recovery_only_observes_terminal_result():
    context, ticket, _, ball, _ = setup_case()
    assert recover(context, ticket) == 'FETCH_BALL_CANCELLED'
    context.backend.reset_operation_counts()
    assert recover(context, ticket) == 'FETCH_BALL_CANCELLED'
    assert context.backend.operation_counts.get('rename', 0) == 0
    assert context.backend.operation_counts.get('replace_text', 0) == 0


def test_rename_conflict_does_not_rewrite_or_clear_evidence():
    context, ticket, _, ball, _ = setup_case()
    before = context.backend.read_text(ball).value.text
    context.backend.inject_outcome('rename', BackendOutcome.CONFLICT)
    with pytest.raises(ReturnRecoveryError):
        recover(context, ticket)
    assert context.backend.read_text(ball).value.text == before
    assert context.backend.get_metadata(ball).value.name == 'FETCH_BALL_RETURNING'


def test_stop_request_prevents_publication():
    context, ticket, _, _, _ = setup_case()
    with pytest.raises(ReturnRecoveryError, match='STOP'):
        recover_returning(context, ticket, now_epoch_s=NOW, stop_requested=lambda: True)
    assert context.backend.operation_counts.get('rename', 0) == 0
