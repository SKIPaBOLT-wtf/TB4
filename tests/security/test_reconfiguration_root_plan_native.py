"""Actual native shared-root-plan cuts; an unknown plan never arms SDK."""
from contextlib import contextmanager
import pytest

from tb4.private_settings import SettingsError
from test_private_settings_native import fixture
from reconfiguration_roots_support import system


@pytest.mark.parametrize("at",["intent","terminal"])
def test_actual_native_shared_root_plan_cut_recovers_exact_original_frame_and_never_reissues_cas(fixture,at):
    root,store = fixture; s = system(effect_store=store)
    locked = store.native.locked; cas = s.value.context.leadership.backend.compare_replace; calls = []
    def count(snapshot,desired):
        calls.append(True); return cas(snapshot,desired)
    s.value.context.leadership.backend.compare_replace = count
    @contextmanager
    def cut():
        with locked() as port:
            promote = port.promote
            def stop():
                payload = store._decode(port.read("settings.pending"),port.binding).payload
                pending,last = payload["pending"],payload["last"]
                if (at == "intent" and pending is not None and pending["purpose"] == "ROOT_PLAN"
                    or at == "terminal" and pending is None and last is not None and last["plan"]["purpose"] == "ROOT_PLAN"):
                    raise OSError("SYNTHETIC_SHARED_PLAN_CUT")
                promote()
            port.promote = stop; yield port
    store.native.locked = cut
    with pytest.raises(SettingsError,match="SETTINGS_STORE_UNAVAILABLE"):
        s.roots.begin(owner_authorized=True)
    store.native.locked = locked; pending = (root/"settings.pending").read_bytes()
    assert not s.moves and len(calls) == (0 if at == "intent" else 1)
    assert s.value.effects.recover_local(owner_authorized=True) == "INSPECT_REQUIRED"
    assert (root/"settings.json").read_bytes() == pending
    assert s.value.effects.inspect() == ("UNKNOWN" if at == "intent" else "NO_PENDING")
    prior = len(calls)
    if at == "intent":
        assert s.roots.advance(owner_authorized=True) == "UNKNOWN" and not s.moves and len(calls) == prior
    else:
        # First metadata dispatch, not a repeat of the shared root-plan CAS.
        s.value.context.leadership.backend.compare_replace = cas
        assert s.roots.advance(owner_authorized=True) == "CONFIRMED" and len(s.moves) == 1 and len(calls) == prior
