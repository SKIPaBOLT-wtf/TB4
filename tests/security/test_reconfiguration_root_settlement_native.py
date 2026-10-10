"""Actual native inherited-receipt cut, synthetic SDK; old host unused."""
from contextlib import contextmanager
from dataclasses import replace
import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import SettingsError, native_settings
from tb4.reconfiguration_effects import Effects
from tb4.reconfiguration_root_settlement import InheritedRootSettlement
from tb4.watchdog.leadership_runtime import Action
from test_private_settings_native import fixture
from test_reconfiguration_root_settlement import inherited


def test_actual_native_inherited_root_receipt_cut_recovers_same_intent_without_old_host_or_sdk(fixture):
    root,store = fixture; s,context,_ = inherited()
    checkpoint_store = native_settings(root.parent/"role-checkpoint",create=True,owner_authorized=True)
    from tb4.watchdog.checkpoint_store import NativeCheckpoint
    checkpoint = NativeCheckpoint(checkpoint_store,installation_id=context.setup.installation_id,
        binding=context.leadership.backend.binding,create=True,owner_authorized=True,initial=context.checkpoint.read())
    effects = Effects(context.leadership,checkpoint,store)
    context = replace(context,checkpoint=checkpoint,effects=effects)
    helper = InheritedRootSettlement(context); proof = helper.inspect(); moves = list(s.moves)
    locked = store.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            def stop():
                raise OSError("SYNTHETIC_INHERITED_RECEIPT_CUT")
            port.promote = stop
            yield port
    store.native.locked = cut
    with pytest.raises(SettingsError,match="SETTINGS_STORE_UNAVAILABLE"):
        helper.settle(proof,owner_authorized=True)
    store.native.locked = locked
    pending = (root/"settings.pending").read_bytes()
    assert context.effects.recover_local(owner_authorized=True) == "INSPECT_REQUIRED"
    assert (root/"settings.json").read_bytes() == pending
    # Only a prepared local receipt intent exists: no CAS may be reissued on resume.
    assert context.effects.inspect() == "UNKNOWN"
    assert context.effects.receipt(Action.IDENTITY)["outcome"] == "UNKNOWN" and s.moves == moves
