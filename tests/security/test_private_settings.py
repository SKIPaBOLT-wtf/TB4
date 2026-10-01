"""Transaction conformance with a synthetic private store; no native claim."""
from contextlib import contextmanager
import copy
import hashlib
import json

import pytest

from tb4.private_settings import PrivateSettings, SettingsError, encoded


class MemoryNative:
    def __init__(self):
        self.files = {}
        self.binding = {"principal": "synthetic-owner", "directory": [1, 2]}
        self.busy = False
        self.failure = None

    @contextmanager
    def locked(self):
        if self.busy:
            raise SettingsError("SETTINGS_BUSY")
        self.busy = True
        try:
            yield self
        finally:
            self.busy = False

    def read(self, name):
        if self.failure == "readback" and name == "settings.json" and name in self.files:
            raise OSError("SYNTHETIC_PRIVATE_CANARY")
        return self.files.get(name)

    def stage(self, raw):
        assert "settings.pending" not in self.files
        self.files["settings.pending"] = raw
        if self.failure == "stage":
            raise OSError("SYNTHETIC_PRIVATE_CANARY")

    def promote(self):
        if self.failure == "promote":
            raise OSError("SYNTHETIC_PRIVATE_CANARY")
        self.files["settings.json"] = self.files.pop("settings.pending")


@pytest.fixture
def fixture():
    native = MemoryNative()
    return native, PrivateSettings(native)


def test_revision_previous_and_restart_are_observations_not_new_identity(fixture):
    native, store = fixture
    assert store.read() is None
    payload = {"installation": "synthetic-first-id", "phase": "INCOMPLETE"}
    first = store.save(payload, expected_revision=0)
    payload["installation"] = "caller-mutation"
    assert first.payload["installation"] == "synthetic-first-id"
    second = PrivateSettings(native).save({**first.payload, "phase": "CANCELLED"}, expected_revision=1)
    assert second.revision == 2 and second.previous == first.payload
    assert PrivateSettings(native).read().payload == second.payload
    assert "synthetic-first-id" not in repr(second)


def test_stale_writer_cannot_replace_newer_state(fixture):
    native, store = fixture
    store.save({"id": "one"}, expected_revision=0)
    before = copy.deepcopy(native.files)
    with pytest.raises(SettingsError, match="CHANGED_RELOAD"):
        store.save({"id": "two"}, expected_revision=0)
    assert native.files == before


@pytest.mark.parametrize("failure", ["stage", "promote"])
def test_interrupted_first_commit_preserves_exact_candidate(fixture, failure):
    native, store = fixture
    native.failure = failure
    with pytest.raises(SettingsError, match="COMMIT_UNCONFIRMED"):
        store.save({"id": "same-id"}, expected_revision=0)
    pending = native.files["settings.pending"]
    native.failure = None
    with pytest.raises(SettingsError, match="RECOVERY_REQUIRED"):
        store.read()
    with pytest.raises(SettingsError, match="RECOVERY_REQUIRED"):
        store.save({"id": "wrong-id"}, expected_revision=0)
    recovered = PrivateSettings(native).recover_pending()
    assert recovered.payload == {"id": "same-id"}
    assert native.files == {"settings.json": pending}
    assert store.recover_pending() == recovered


def test_lost_readback_inspects_committed_state_without_replay(fixture):
    native, store = fixture
    native.failure = "readback"
    with pytest.raises(SettingsError, match="COMMIT_UNCONFIRMED"):
        store.save({"id": "one"}, expected_revision=0)
    native.failure = None
    assert store.read().revision == 1
    with pytest.raises(SettingsError, match="CHANGED_RELOAD"):
        store.save({"id": "another"}, expected_revision=0)


def test_recovery_refuses_an_unrelated_or_stale_candidate(fixture):
    native, store = fixture
    store.save({"id": "one"}, expected_revision=0)
    old = native.files["settings.json"]
    store.save({"id": "one", "phase": "next"}, expected_revision=1)
    native.files["settings.pending"] = old
    before = copy.deepcopy(native.files)
    with pytest.raises(SettingsError, match="RECOVERY_CONFLICT"):
        store.recover_pending()
    assert native.files == before


def test_pending_update_blocks_reading_a_stale_current_payload(fixture):
    native, store = fixture
    store.save({"id": "one"}, expected_revision=0)
    native.failure = "promote"
    with pytest.raises(SettingsError):
        store.save({"id": "one", "phase": "new"}, expected_revision=1)
    native.failure = None
    with pytest.raises(SettingsError, match="RECOVERY_REQUIRED"):
        store.read()
    assert store.recover_pending().payload["phase"] == "new"


@pytest.mark.parametrize("raw", [b"", b"{", b'{"schema_version":1,"schema_version":1}',
                                  b'{"x":NaN}', b"[]" ],
                         ids=["empty", "partial", "duplicate", "nonfinite", "array"])
def test_partial_or_malformed_pending_is_preserved(fixture, raw):
    native, store = fixture
    native.files["settings.pending"] = raw
    with pytest.raises(SettingsError):
        store.recover_pending()
    with pytest.raises(SettingsError):
        store.save({"id": "must-not-recreate"}, expected_revision=0)
    assert native.files == {"settings.pending": raw}


def test_copying_state_to_another_directory_or_owner_fails(fixture):
    native, store = fixture
    store.save({"id": "one"}, expected_revision=0)
    native.binding = {"principal": "synthetic-other", "directory": [1, 3]}
    with pytest.raises(SettingsError, match="IDENTITY_MISMATCH"):
        store.read()


def test_payload_corruption_cannot_be_read_or_overwritten(fixture):
    native, store = fixture
    store.save({"id": "one"}, expected_revision=0)
    frame = json.loads(native.files["settings.json"])
    frame["payload"] = {"id": "changed"}
    native.files["settings.json"] = encoded(frame)
    with pytest.raises(SettingsError, match="DIGEST_MISMATCH"):
        store.read()
    with pytest.raises(SettingsError, match="DIGEST_MISMATCH"):
        store.save({"id": "replacement"}, expected_revision=1)


def test_counter_exhaustion_does_not_stage_an_unreadable_frame(fixture):
    native, store = fixture
    store.save({"id": "one"}, expected_revision=0)
    frame = json.loads(native.files["settings.json"])
    frame["revision"] = 2**63 - 1
    frame.pop("digest")
    frame["digest"] = hashlib.sha256(encoded(frame)).hexdigest()
    native.files["settings.json"] = encoded(frame)
    before = copy.deepcopy(native.files)
    with pytest.raises(SettingsError, match="REVISION_EXHAUSTED"):
        store.save({"id": "next"}, expected_revision=2**63 - 1)
    assert native.files == before


@pytest.mark.parametrize("payload", [{"value": float("nan")}, {"value": "x" * (1024 * 1024)}],
                         ids=["nonfinite", "oversized"])
def test_invalid_payload_never_stages(fixture, payload):
    native, store = fixture
    with pytest.raises(SettingsError):
        store.save(payload, expected_revision=0)
    assert not native.files


def test_concurrent_lock_and_provider_errors_do_not_leak(fixture, capsys):
    native, store = fixture
    with native.locked():
        with pytest.raises(SettingsError, match="BUSY"):
            store.save({"id": "one"}, expected_revision=0)
    native.failure = "promote"
    with pytest.raises(SettingsError) as error:
        store.save({"private": "SYNTHETIC_PRIVATE_CANARY"}, expected_revision=0)
    assert str(error.value) == "SETTINGS_COMMIT_UNCONFIRMED"
    assert "CANARY" not in repr(error.value)
    assert capsys.readouterr() == ("", "")
