"""Actual protected adopted-WAL/evidence cuts, synthetic SDK without old host."""
from contextlib import contextmanager
import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.private_settings import SettingsError
from tb4.reconfiguration_root_resume import ResumedDocsRootMoves
from reconfiguration_root_resume_support import system,adopter
from test_private_settings_native import fixture


@pytest.mark.parametrize("at",["begin","invoking","completed"])
def test_actual_native_adopted_wal_cut_recovers_exact_frame_without_metadata_reissue(fixture,at):
    root,store=fixture;s=system();s.roots.begin(owner_authorized=True)
    r=adopter(s,store=store);profile=r.ctx.setup.store.read();locked=store.native.locked
    if at!="begin":
        r.begin(r.inspector.inspect(),owner_authorized=True)
    @contextmanager
    def cut():
        with locked() as port:
            promote=port.promote
            def stop():
                payload=store._decode(port.read("settings.pending"),port.binding).payload
                if (at=="begin" or at=="invoking" and payload["pending"] is not None
                    and payload["pending"]["dispatch"]=="INVOKING"
                    or at=="completed" and payload["index"]==1):
                    raise OSError("SYNTHETIC_ADOPTED_NATIVE_CUT")
                promote()
            port.promote=stop;yield port
    store.native.locked=cut
    with pytest.raises(SettingsError,match="SETTINGS_STORE_UNAVAILABLE"):
        if at=="begin":r.begin(r.inspector.inspect(),owner_authorized=True)
        else:r.advance(owner_authorized=True)
    store.native.locked=locked;pending=(root/"settings.pending").read_bytes()
    expected_moves=1 if at=="completed" else 0
    assert len(s.moves)==expected_moves and r.ctx.setup.store.read()==profile
    assert r.recover_local(owner_authorized=True)=="INSPECT_REQUIRED"
    assert (root/"settings.json").read_bytes()==pending
    fresh=ResumedDocsRootMoves(r.context)
    if at=="invoking":
        assert fresh.advance(owner_authorized=True)=="UNKNOWN" and not s.moves
        with pytest.raises(ConfigurationError,match="NOT_PREPARED"):
            fresh.revoke_prepared(owner_authorized=True)
    elif at=="completed":
        assert fresh.inspect()=="MOVING" and len(s.moves)==1
    else:
        assert fresh.inspect()=="MOVING" and not s.moves
    assert r.ctx.setup.store.read()==profile


def test_actual_native_first_evidence_cut_promotes_exact_image_without_adoption_or_sdk(fixture):
    root,store=fixture;s=system();s.roots.begin(owner_authorized=True)
    r=adopter(s,evidence_store=store);profile=r.ctx.setup.store.read();locked=store.native.locked
    @contextmanager
    def cut():
        with locked() as port:
            def stop():raise OSError("SYNTHETIC_ADOPTED_EVIDENCE_CUT")
            port.promote=stop;yield port
    store.native.locked=cut
    with pytest.raises(ConfigurationError,match="EVIDENCE_UNCONFIRMED"):
        r.begin(r.inspector.inspect(),owner_authorized=True)
    store.native.locked=locked;pending=(root/"settings.pending").read_bytes()
    assert r.context.store.read() is None and not s.moves
    assert r.recover_evidence(owner_authorized=True)=="INSPECT_REQUIRED"
    assert (root/"settings.json").read_bytes()==pending and not s.moves
    assert r.begin(r.inspector.inspect(),owner_authorized=True)=="MOVING" and not s.moves
    assert r.ctx.setup.store.read()==profile
