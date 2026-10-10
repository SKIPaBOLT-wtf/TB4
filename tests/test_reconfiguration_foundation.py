"""Behavioral boundaries of the unreleased foundation, not C1 acceptance."""
import copy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from tb4.configuration_contract import ConfigurationError, configuration, marker, require_dispatch
from tb4.drive.authority_transaction import OwnerGuard, RecordMutation, reconcile
from tb4.drive.docs_authority import NativeDocsAuthority
from tb4.exchange_layout import Capacity, empty_document
from tb4.private_settings import PrivateSettings
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_inspection import inspect
from tb4.watchdog.leadership_runtime import Action, Checkpoint, Receipt
from tests.reconfiguration_support import CANARY, TRANSITION, configure, image, setup
from tests.security.test_private_settings import MemoryNative
from tests.drive.test_native_docs_transport import BINDING, DOMAIN, WireStore


def test_closed_marker_schema_matches_runtime_and_legacy_absence():
    from jsonschema import Draft202012Validator
    validator = Draft202012Validator(json.loads((Path(__file__).parents[1] /
        "protocol/configuration-v1.schema.json").read_text()))
    good = configure(empty_document(DOMAIN))["records"]["global.settings"]["body"]["configuration"]
    cases = [good, {**good, "revision": True}, {**good, "revision": 0},
             {**good, "revision": 2**63}, {**good, "phase": "READY"},
             {**good, "transition_id": "private"}, {**good, "host": CANARY},
             {**good, "schema_version": True}, None]
    for value in cases:
        valid = validator.is_valid(value)
        if valid:
            assert marker(value) == value
        else:
            with pytest.raises(ConfigurationError):
                marker(value)
    legacy = empty_document(DOMAIN)
    assert configuration(legacy) is None
    assert require_dispatch(legacy) is None
    with pytest.raises(ConfigurationError, match="REVISION_REQUIRED"):
        require_dispatch(legacy, 1)


@pytest.mark.parametrize("revision", [None, True, 0, 2, 2**63])
def test_active_marker_requires_actual_matching_local_revision(revision):
    doc = configure(empty_document(DOMAIN), "ACTIVE")
    with pytest.raises(ConfigurationError, match="REVISION_REQUIRED"):
        require_dispatch(doc, revision)
    assert require_dispatch(doc, 1) is None


def test_inspection_preserves_unread_unknown_and_local_effects_without_leaking_identities():
    value, doc = setup(), empty_document(DOMAIN, Capacity(2, 2, 2, 2))
    for i, retention in enumerate(("BUSY", "UNREAD", "UNKNOWN")):
        key = ("target.000.work", "target.000.result", "artifact.000.input")[i]
        doc["records"][key] = dict(generation=7, operation_id=TRANSITION,
                                   retention=retention, body={"private": CANARY})
    payload = copy.deepcopy(value._payload)
    payload["operations"]["d" * 64] = "UNKNOWN"
    checkpoint = Checkpoint(receipts=(Receipt(Action.SSH, "e" * 64, 1, "UNKNOWN"),))
    snapshot = image(doc)
    result = inspect(snapshot, setup_payload=payload, checkpoint=checkpoint)
    public = json.dumps(result.public_summary(), sort_keys=True)
    assert result.public_summary()["counts"] == dict(LOCAL_EFFECT_UNKNOWN=1, LOCAL_SETUP_UNKNOWN=1,
        SHARED_BUSY=1, SHARED_UNKNOWN=1, SHARED_UNREAD=1)
    for secret in (CANARY, BINDING.document_id, value.installation_id, snapshot.revision,
                   result.raw_sha256, TRANSITION):
        assert secret not in public and secret not in repr(result)
    assert snapshot.document() == doc and value._payload["operations"] == {}


def test_stable_unknown_facts_and_retained_metadata_are_not_work_blockers():
    value = setup()
    result = inspect(image(), setup_payload=value._payload, checkpoint=Checkpoint())
    assert result.public_summary()["counts"] == {}
    # Stable-IP UNKNOWN is tested through the actual validated local-table package
    # in RP026 regressions; this inspector never scans arbitrary UNKNOWN strings.
    assert not result.public_summary()["requires_resolution"]


def test_foreign_local_authority_and_malformed_checkpoint_refuse():
    value = setup()
    foreign = copy.deepcopy(value._payload)
    foreign["choices"]["storage"]["authority"]["object_id"] = "other-doc"
    with pytest.raises(ConfigurationError, match="LOCAL_BINDING"):
        inspect(image(), setup_payload=foreign, checkpoint=Checkpoint())
    with pytest.raises(ConfigurationError, match="LOCAL_CHECKPOINT"):
        inspect(image(), setup_payload=value._payload, checkpoint=Checkpoint(receipts=["UNKNOWN"]))


def test_evidence_needs_owner_is_immutable_and_binds_exact_readback():
    value, native = setup(), MemoryNative()
    snapshot = image()
    inspection = inspect(snapshot, setup_payload=value._payload, checkpoint=Checkpoint())
    archive = ProtectedEvidence(PrivateSettings(native), installation_id=value.installation_id,
                                transition_id=TRANSITION)
    with pytest.raises(ConfigurationError, match="OWNER_REQUIRED"):
        archive.preserve(snapshot, inspection)
    assert not native.files
    receipt = archive.preserve(snapshot, inspection, owner_authorized=True)
    before = copy.deepcopy(native.files)
    assert archive.preserve(snapshot, inspection, owner_authorized=True) == receipt
    assert native.files == before and archive.read(receipt)["inspection"] == inspection.private_record()
    other = image(configure(snapshot.document()))
    changed = inspect(other, setup_payload=value._payload, checkpoint=Checkpoint())
    with pytest.raises(ConfigurationError, match="IMMUTABLE"):
        archive.preserve(other, changed, owner_authorized=True)
    with pytest.raises(ConfigurationError, match="CHANGED"):
        archive.read(replace(receipt, payload_sha256="f" * 64))
    assert native.files == before and value.installation_id not in repr(archive)


@pytest.mark.parametrize("failure", ["stage", "promote", "readback"])
def test_lost_evidence_commit_is_inspect_only_not_overwritten(failure):
    value, native = setup(), MemoryNative()
    snapshot = image()
    inspection = inspect(snapshot, setup_payload=value._payload, checkpoint=Checkpoint())
    archive = ProtectedEvidence(PrivateSettings(native), installation_id=value.installation_id,
                                transition_id=TRANSITION)
    native.failure = failure
    with pytest.raises(ConfigurationError, match="UNCONFIRMED"):
        archive.preserve(snapshot, inspection, owner_authorized=True)
    before = copy.deepcopy(native.files)
    native.failure = None
    if failure == "readback":
        assert archive.preserve(snapshot, inspection, owner_authorized=True)
    else:
        with pytest.raises(ConfigurationError, match="UNCONFIRMED"):
            archive.preserve(snapshot, inspection, owner_authorized=True)
    assert native.files == before


def test_shared_plan_prepared_before_maintenance_cannot_cross_cas_race():
    doc = empty_document(DOMAIN, Capacity(2, 2, 2, 2))
    owner = OwnerGuard("synthetic-owner", 1)
    doc["records"]["global.leadership"] = dict(generation=1, operation_id="a" * 64,
        retention="BUSY", body=dict(owner=owner.owner, epoch=1, phase="ACTIVE"))
    wire = WireStore(doc)
    backend = NativeDocsAuthority(wire.client(), BINDING)
    plan = RecordMutation.prepare(backend.read(), owner=owner, protect=set(), changes={
        "global.summary": dict(generation=1, operation_id=TRANSITION, retention="BUSY", body={"count":1})})
    def enter(_):
        configure(wire.document)
        wire.bump()
    wire.before_write = enter
    report = reconcile(backend, plan, mode="START")
    assert report.outcome == "CONFLICT" and wire.commits == 0 and len(wire.calls) == 1
    assert wire.document["records"]["global.summary"]["retention"] == "FREE"
    with pytest.raises(Exception, match="MAINTENANCE"):
        RecordMutation.prepare(backend.read(), owner=owner, protect=set(), changes={
            "global.summary": dict(generation=1, operation_id=TRANSITION, retention="BUSY", body={})})


def test_active_configuration_change_invalidates_prepared_record_plan():
    doc = configure(empty_document(DOMAIN), "ACTIVE")
    owner = OwnerGuard("synthetic-owner", 1)
    doc["records"]["global.leadership"] = dict(generation=1, operation_id="a" * 64,
        retention="BUSY", body=dict(owner=owner.owner, epoch=1, phase="ACTIVE"))
    wire = WireStore(doc)
    backend = NativeDocsAuthority(wire.client(), BINDING)
    plan = RecordMutation.prepare(backend.read(), owner=owner, protect=set(), changes={
        "global.summary": dict(generation=1, operation_id=TRANSITION, retention="BUSY", body={})})
    configure(wire.document, "ACTIVE", 2)
    wire.bump()
    assert plan.evaluate(backend.read())[0] == "CONFLICT"
