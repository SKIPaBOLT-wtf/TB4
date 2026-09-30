"""Explicit publication recovery, never execution recovery.

The caller must hold the local FETCHER worker lock and exclude other launchers.
A reviewed ticket pins one result and an independent BONEYARD copy. A stale
heartbeat is an additional guard, not proof that an arbitrary OS child is dead.
Only the existing FETCHER RETURNING -> recorded-terminal edge is used. Nothing
is executed, reclassified, cleared, recycled, or silently completed at startup.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Callable, Mapping

from tb4.core.fencing import FenceToken
from tb4.core.models import Generation, ObjectStateRef, OperationId
from tb4.core.protocol_names import LogicalObject, Role
from tb4.core.schemas import canonical_json_text, load_schema_store
from tb4.drive.errors import BackendOutcome, BackendResult
from tb4.drive.state_walker import StateWalker
from tb4.runtime_support import RuntimeContext


class ReturnRecoveryError(RuntimeError):
    """Only public-safe codes are emitted; payload/provider text stays private."""


def validate_ticket(ticket: Any) -> dict[str, Any]:
    keys = {'operation_id', 'generation', 'result_sha256', 'archive_id', 'reviewed'}
    if not isinstance(ticket, Mapping) or set(ticket) != keys:
        raise ReturnRecoveryError('RETURN_RECOVERY_TICKET_INVALID')
    value = dict(ticket)
    if value['reviewed'] is not True or type(value['generation']) is not int or value['generation'] < 0:
        raise ReturnRecoveryError('RETURN_RECOVERY_TICKET_INVALID')
    operation = value['operation_id']
    digest = value['result_sha256']
    archive = value['archive_id']
    if not isinstance(operation, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{8,128}', operation):
        raise ReturnRecoveryError('RETURN_RECOVERY_TICKET_INVALID')
    if not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise ReturnRecoveryError('RETURN_RECOVERY_TICKET_INVALID')
    if not isinstance(archive, str) or not 1 <= len(archive) <= 256 or archive.strip() != archive:
        raise ReturnRecoveryError('RETURN_RECOVERY_TICKET_INVALID')
    return value


def recover_returning(
    context: RuntimeContext,
    ticket: Mapping[str, Any],
    *,
    now_epoch_s: int,
    monotonic_now: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    stop_requested: Callable[[], bool] = lambda: False,
) -> str:
    """Finalize exactly a reviewed, already-written report; preserve its bytes.

    This does not certify that the recorded outcome satisfied the user's goal.
    In particular, publishing a recorded CANCELLED report does not turn a late
    cancellation experiment into a passed cancellation test.
    """
    reviewed = validate_ticket(ticket)
    if type(now_epoch_s) is not int or now_epoch_s <= 0:
        raise ReturnRecoveryError('RETURN_RECOVERY_CLOCK_INVALID')
    backend = context.backend
    park = context.park_map
    device_id = context.config['identity']['device_id']
    ball_id = park.lookup_device(device_id, 'PLAYGROUND.FETCH_BALL')
    playground_id = park.lookup_device(device_id, 'PLAYGROUND')
    boneyard_id = park.lookup_device(device_id, 'BONEYARD')
    pulse_id = park.lookup_device(device_id, 'DOG_PULSE')
    archive_id = reviewed['archive_id']
    if archive_id == ball_id or archive_id in park.entries.values():
        raise ReturnRecoveryError('RETURN_RECOVERY_ARCHIVE_INVALID')
    store = load_schema_store()

    def read_stable(object_id: str):
        remote = backend.read_text(object_id)
        if not remote.ok or remote.value is None:
            raise ReturnRecoveryError('RETURN_RECOVERY_READ_FAILED')
        item = remote.value
        if item.metadata.is_folder or item.metadata.object_id != object_id:
            raise ReturnRecoveryError('RETURN_RECOVERY_OBJECT_INVALID')
        if len(item.text.encode('utf-8')) > 65_536:
            raise ReturnRecoveryError('RETURN_RECOVERY_BODY_TOO_LARGE')
        after = backend.get_metadata(object_id)
        if not after.ok or after.value is None:
            raise ReturnRecoveryError('RETURN_RECOVERY_READ_FAILED')
        if (
            item.metadata.version_token is None
            or after.value.version_token != item.metadata.version_token
            or after.value.name != item.metadata.name
            or after.value.parent_ids != item.metadata.parent_ids
            or after.value.is_folder
            or after.value.object_id != object_id
        ):
            raise ReturnRecoveryError('RETURN_RECOVERY_OBSERVATION_CHANGED')
        return item

    def verified_body(text: str) -> dict[str, Any]:
        try:
            body = json.loads(text)
            store.validate('fetch-ball.schema.json', body)
        except Exception as exc:
            raise ReturnRecoveryError('RETURN_RECOVERY_BODY_INVALID') from exc
        if (
            body['operation_id'] != reviewed['operation_id']
            or body['generation'] != reviewed['generation']
            or body['result_sha256'] != reviewed['result_sha256']
        ):
            raise ReturnRecoveryError('RETURN_RECOVERY_IDENTITY_MISMATCH')
        if body['result_code'] not in {'DONE', 'PARTIAL', 'FAILED', 'CANCELLED'}:
            raise ReturnRecoveryError('RETURN_RECOVERY_RESULT_INCOMPLETE')
        if body['started_at'] <= 0 or body['finished_at'] < body['started_at']:
            raise ReturnRecoveryError('RETURN_RECOVERY_RESULT_INCOMPLETE')
        unhashed = dict(body)
        unhashed['result_sha256'] = None
        digest = hashlib.sha256(canonical_json_text(unhashed).encode('utf-8')).hexdigest()
        if digest != reviewed['result_sha256']:
            raise ReturnRecoveryError('RETURN_RECOVERY_HASH_MISMATCH')
        if body['payload_source'] == 'INLINE':
            payload_digest = hashlib.sha256(body['inline_payload'].encode('utf-8')).hexdigest()
            if payload_digest != body['payload_sha256']:
                raise ReturnRecoveryError('RETURN_RECOVERY_PAYLOAD_HASH_MISMATCH')
        return body

    def checkpoint() -> None:
        if stop_requested():
            raise ReturnRecoveryError('RETURN_RECOVERY_STOP_REQUESTED')
        pulse = read_stable(pulse_id)
        try:
            value = json.loads(pulse.text)
            store.validate('dog-pulse.schema.json', value)
        except Exception as exc:
            raise ReturnRecoveryError('RETURN_RECOVERY_PULSE_INVALID') from exc
        if value['device_id'] != device_id:
            raise ReturnRecoveryError('RETURN_RECOVERY_PULSE_INVALID')
        defaults = context.defaults
        horizon = max(
            int(defaults['watchdog']['stale_idle_s']),
            int(defaults['watchdog']['stale_active_s']),
        ) + int(defaults['fetcher']['gone_grace_s'])
        # Future or recently refreshed pulses also fail closed. Use the fixed
        # action-start epoch so a long action cannot age a fresh peer into safety.
        if now_epoch_s - value['emitted_at'] <= horizon:
            raise ReturnRecoveryError('RETURN_RECOVERY_PULSE_FRESH')

    checkpoint()
    archived = read_stable(archive_id)
    if archived.metadata.parent_ids != (boneyard_id,):
        raise ReturnRecoveryError('RETURN_RECOVERY_ARCHIVE_INVALID')
    recorded = verified_body(archived.text)
    terminal = recorded['result_code']
    terminal_name = 'FETCH_BALL_' + terminal

    def read_live():
        current = read_stable(ball_id)
        if current.metadata.parent_ids != (playground_id,):
            raise ReturnRecoveryError('RETURN_RECOVERY_OBJECT_INVALID')
        if current.metadata.name not in {'FETCH_BALL_RETURNING', terminal_name}:
            raise ReturnRecoveryError('RETURN_RECOVERY_STATE_INVALID')
        verified_body(current.text)
        if current.text != archived.text:
            raise ReturnRecoveryError('RETURN_RECOVERY_ARCHIVE_MISMATCH')
        return current

    initial = read_live()
    if initial.metadata.name == terminal_name:
        return terminal_name

    def fence_reader(object_id: str):
        try:
            if object_id != ball_id:
                raise ReturnRecoveryError('RETURN_RECOVERY_OBJECT_INVALID')
            checkpoint()
            current = read_live()
            if current.metadata.name != 'FETCH_BALL_RETURNING':
                raise ReturnRecoveryError('RETURN_RECOVERY_OBSERVATION_CHANGED')
            archive_now = backend.get_metadata(archive_id)
            if (
                not archive_now.ok or archive_now.value is None
                or archive_now.value.version_token != archived.metadata.version_token
                or archive_now.value.parent_ids != (boneyard_id,)
            ):
                raise ReturnRecoveryError('RETURN_RECOVERY_ARCHIVE_CHANGED')
            return BackendResult.success(FenceToken(
                ball_id, OperationId(reviewed['operation_id']), Generation(reviewed['generation']),
                ObjectStateRef(LogicalObject.FETCH_BALL, 'RETURNING'),
            ))
        except ReturnRecoveryError as exc:
            return BackendResult.failure(BackendOutcome.CONFLICT, message=str(exc))

    walker = StateWalker(backend, context.retry_policy, monotonic_now, sleeper)
    expected = FenceToken(
        ball_id, OperationId(reviewed['operation_id']), Generation(reviewed['generation']),
        ObjectStateRef(LogicalObject.FETCH_BALL, 'RETURNING'),
    )
    checkpoint()
    report = walker.walk(
        object_id=ball_id, logical_object=LogicalObject.FETCH_BALL,
        expected_state='RETURNING', target_state=terminal, actor=Role.FETCHER,
        expected_fence=expected, fence_reader=fence_reader,
    )
    if not report.success:
        raise ReturnRecoveryError('RETURN_RECOVERY_PUBLICATION_UNCONFIRMED')
    if read_live().metadata.name != terminal_name:
        raise ReturnRecoveryError('RETURN_RECOVERY_PUBLICATION_UNCONFIRMED')
    return terminal_name
