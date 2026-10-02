"""Fresh synthetic native protected evidence only; no live settings changes."""
import base64
from dataclasses import replace
import sys

import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import MAX_BYTES, native_settings
from tb4.exchange_layout import Capacity, empty_document, slots
from tb4.reconfiguration_evidence import ProtectedEvidence
from tb4.reconfiguration_inspection import inspect
from tb4.watchdog.leadership_runtime import Checkpoint
from reconfiguration_support import TRANSITION, image, setup
from test_native_docs_transport import DOMAIN
from test_private_settings_native import fixture, protect_fixture  # noqa: F401

pytestmark = pytest.mark.skipif(sys.platform not in {"win32", "linux"}, reason="native Windows/Linux64")


def capture(store):
    value, snapshot = setup(), image()
    facts = inspect(snapshot, setup_payload=value._payload, checkpoint=Checkpoint())
    archive = ProtectedEvidence(store, installation_id=value.installation_id, transition_id=TRANSITION)
    receipt = archive.preserve(snapshot, facts, owner_authorized=True)
    return archive, receipt, snapshot


def test_actual_private_restart_returns_same_bytes_and_binding(fixture, capsys):
    root, store = fixture
    archive, receipt, snapshot = capture(store)
    restarted = ProtectedEvidence(native_settings(root), installation_id=receipt.installation_id,
                                  transition_id=TRANSITION)
    assert base64.b64decode(restarted.read(receipt)["image"]) == snapshot.raw
    assert store.read().revision == 1
    assert capsys.readouterr() == ("", "")


def test_actual_copied_file_lock_and_broad_permissions_are_refused(fixture):
    root, store = fixture
    archive, receipt, _ = capture(store)
    with store.native.locked():
        with pytest.raises(ConfigurationError, match="UNCONFIRMED"):
            archive.read(receipt)
    other = root.parent / "copied-evidence"
    other_store = native_settings(other, create=True, owner_authorized=True)
    target = other / "settings.json"
    target.write_bytes((root / "settings.json").read_bytes())
    protect_fixture(target)
    copied = ProtectedEvidence(other_store, installation_id=receipt.installation_id, transition_id=TRANSITION)
    with pytest.raises(ConfigurationError, match="UNCONFIRMED"):
        copied.read(receipt)
    protect_fixture(root, broad=True)
    try:
        with pytest.raises(ConfigurationError, match="UNCONFIRMED"):
            archive.read(receipt)
    finally:
        protect_fixture(root)


def test_actual_mid_promotion_leaves_exact_pending_without_replay(fixture):
    from contextlib import contextmanager
    root, store = fixture
    original = store.native.locked
    @contextmanager
    def stop():
        with original() as port:
            def fail():
                raise OSError("SYNTHETIC_PRIVATE_CANARY")
            port.promote = fail
            yield port
    store.native.locked = stop
    value, snapshot = setup(), image()
    facts = inspect(snapshot, setup_payload=value._payload, checkpoint=Checkpoint())
    archive = ProtectedEvidence(store, installation_id=value.installation_id, transition_id=TRANSITION)
    with pytest.raises(ConfigurationError, match="UNCONFIRMED"):
        archive.preserve(snapshot, facts, owner_authorized=True)
    pending = (root / "settings.pending").read_bytes()
    store.native.locked = original
    with pytest.raises(ConfigurationError, match="UNCONFIRMED"):
        archive.preserve(snapshot, facts, owner_authorized=True)
    assert (root / "settings.pending").read_bytes() == pending
    assert not (root / "settings.json").exists()


def test_large_unicode_authority_fits_one_native_frame_without_previous_copy(fixture):
    root, store = fixture
    capacity = Capacity(64, 16, 128, 32)
    value, document = setup(capacity), empty_document(DOMAIN, capacity)
    for key, budget in slots(capacity).items():
        document["records"][key] = dict(generation=1, operation_id=TRANSITION,
            retention="RETAINED", body={"text": "\u6f22" * ((budget - 180) // 3)})
    snapshot = image(document)
    assert len(snapshot.raw) > 400000
    facts = inspect(snapshot, setup_payload=value._payload, checkpoint=Checkpoint())
    archive = ProtectedEvidence(store, installation_id=value.installation_id, transition_id=TRANSITION)
    receipt = archive.preserve(snapshot, facts, owner_authorized=True)
    assert len((root / "settings.json").read_bytes()) < MAX_BYTES
    assert store.read().previous is None
    assert base64.b64decode(archive.read(receipt)["image"]) == snapshot.raw


def test_full_capacity_unknown_work_is_archived_in_one_native_frame(fixture):
    root, store = fixture
    capacity = Capacity(64, 16, 128, 32)
    value, document = setup(capacity), empty_document(DOMAIN, capacity)
    for key in document["records"]:
        document["records"][key] = dict(generation=1, operation_id=TRANSITION,
            retention="UNKNOWN", body={"private":"SYNTHETIC_PRIVATE_CANARY"})
    snapshot = image(document)
    facts = inspect(snapshot, setup_payload=value._payload, checkpoint=Checkpoint())
    assert len(facts.blockers) == 689
    archive = ProtectedEvidence(store, installation_id=value.installation_id, transition_id=TRANSITION)
    receipt = archive.preserve(snapshot, facts, owner_authorized=True)
    assert len((root/"settings.json").read_bytes()) < MAX_BYTES
    assert len(archive.read(receipt)["inspection"]["blockers"]) == 689
