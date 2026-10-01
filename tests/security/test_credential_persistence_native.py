"""Native restart restores metadata only; external key bytes stay at their source."""
import json
import os

import pytest

from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.credential_persistence import export_private, restore_private
from tb4.private_settings import native_settings
from test_private_settings_native import fixture, protect_fixture

INSTALLATION = "00000000-0000-4000-8000-000000000022"
TARGET = "00000000-0000-4000-8000-000000000023"
TRUST = "d" * 64
CANARY = b"synthetic-external-key-material-never-copied"


class Runner:
    def verify_target(self, target, trust):
        return target == TARGET and trust == TRUST
    def fetcher_status(self, *args):
        raise AssertionError("credential-use callback must never run in setup qualification")
    fetcher_start = fetcher_status


def pair(now=100):
    if os.name == "nt":
        from tb4.windows_key_native import WindowsKeyNative
        from tb4.windows_credentials import WindowsKeyStore
        native, kind = WindowsKeyNative(), WindowsKeyStore
    else:
        from tb4.linux_key_native import LinuxKeyNative
        from tb4.linux_credentials import LinuxKeyStore
        native, kind = LinuxKeyNative(), LinuxKeyStore
    store = kind(INSTALLATION, native=native, runner=Runner(), clock=lambda:now)
    return store, CredentialResolver(INSTALLATION,store,clock=lambda:now)


@pytest.mark.parametrize("change,expected", [
    ("none",Outcome.READY),("rotated",Outcome.REVOKED),("expired",Outcome.EXPIRED),
    ("revoked",Outcome.REVOKED),
])
def test_actual_native_restore_rechecks_original_external_key(fixture, change, expected, capsys):
    root, settings = fixture
    path = root.parent / "synthetic-external-key"
    path.write_bytes(CANARY)
    protect_fixture(path)
    store, resolver = pair()
    extra = dict(interactive_required=False) if os.name == "nt" else dict(
        access_mode="existing_key",launch_mode="headless")
    reference = store.select(path=str(path),target_id=TARGET,target_trust=TRUST,
        purposes=frozenset(Purpose),expires_at=200,owner_authorized=True,**extra)
    handle = resolver.enroll(target_id=TARGET,target_trust=TRUST,store_locator=reference,
        purposes=frozenset(Purpose),expires_at=200,owner_authorized=True)
    if change == "revoked":
        resolver.revoke(handle,owner_authorized=True)
    settings.save({"registry":export_private(store,resolver)},expected_revision=0)
    if change == "rotated":
        path.write_bytes(b"synthetic-other-key")
    fresh_store, fresh_resolver = pair(now=300 if change=="expired" else 100)
    saved = native_settings(root).read().payload
    restore_private(saved["registry"],fresh_store,fresh_resolver)
    report = fresh_resolver.capability(handle,purpose=Purpose.FETCHER_STATUS,
        target_id=TARGET,target_trust=TRUST).report()
    assert report["outcome"] == expected.value
    assert fresh_resolver._bindings[handle].store_locator == reference
    assert CANARY not in (root/"settings.json").read_bytes()
    assert all(value not in json.dumps(report) for value in (str(path),handle,reference))
    assert capsys.readouterr() == ("","")
