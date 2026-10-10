"""Actual native root and cancel-intent cuts; no ambiguous provider reissue."""
from contextlib import contextmanager
from dataclasses import replace
import pytest

from tb4.private_settings import SettingsError,native_settings
from tb4.reconfiguration_effects import Effects
from tb4.reconfiguration_root_settlement import ProvenNoDispatchSettlement
from tb4.watchdog.leadership_runtime import Action
from test_private_settings_native import fixture
from reconfiguration_roots_support import system
from test_reconfiguration_root_no_dispatch import revoked


def test_actual_native_revoked_root_cancel_intent_cut_is_exact_and_inspect_only(fixture):
    root,root_store = fixture
    s,proof = revoked(system(root_store=root_store))
    effect_store = native_settings(root.parent/"cancel-effects",create=True,owner_authorized=True)
    effects = Effects(s.value.context.leadership,s.value.context.checkpoint,effect_store)
    ctx = replace(s.value.context,effects=effects); helper = ProvenNoDispatchSettlement(ctx)
    locked = effect_store.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            def stop():
                raise OSError("SYNTHETIC_NATIVE_CANCEL_CUT")
            port.promote = stop; yield port
    effect_store.native.locked = cut
    with pytest.raises(SettingsError,match="SETTINGS_STORE_UNAVAILABLE"):
        helper.settle(proof,owner_authorized=True)
    effect_store.native.locked = locked
    pending = (root.parent/"cancel-effects"/"settings.pending").read_bytes()
    assert effects.recover_local(owner_authorized=True) == "INSPECT_REQUIRED"
    assert (root.parent/"cancel-effects"/"settings.json").read_bytes() == pending
    assert effects.inspect() == "UNKNOWN"
    assert effects.receipt(Action.IDENTITY)["outcome"] == "UNKNOWN" and not s.moves
    assert s.roots.require_revocation(proof) == proof
