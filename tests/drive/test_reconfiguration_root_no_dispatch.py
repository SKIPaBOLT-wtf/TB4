"""Only actual native non-dispatch permits a separately armed root retry."""
import copy
from dataclasses import replace
import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError
from tb4.private_settings import SettingsError
from tb4.reconfiguration_root_settlement import ProvenNoDispatchSettlement
from tb4.watchdog.leadership_runtime import Action
from reconfiguration_roots_support import system
from test_reconfiguration_effects import acquire_fallback
from test_reconfiguration_roots import updates


def revoked(s=None):
    s = s or system(); s.roots.begin(owner_authorized=True)
    start = s.value.effects.start
    def pause(*args,**kwargs):
        result = start(*args,**kwargs)
        assert result == "CONFIRMED"
        raise ConfigurationError("SYNTHETIC_AFTER_SHARED_BEFORE_SEND")
    s.value.effects.start = pause
    try:
        with pytest.raises(ConfigurationError,match="SYNTHETIC_AFTER_SHARED_BEFORE_SEND"):
            s.roots.advance(owner_authorized=True)
    finally:
        s.value.effects.start = start
    proof = s.roots.revoke_prepared(owner_authorized=True)
    assert not updates(s) and s.value.effects.receipt(Action.IDENTITY)["outcome"] == "UNKNOWN"
    return s,proof


@pytest.mark.parametrize("fallback",[False,True])
def test_exact_native_revocation_settles_only_shared_row_and_retains_original_operation(fallback):
    s,proof = revoked(); context = acquire_fallback(s.value)[2] if fallback else s.value.context
    helper = ProvenNoDispatchSettlement(context)
    before = copy.deepcopy(s.value.provider.store.document); original = s.value.setup.store.read()
    old = s.value.effects.receipt(Action.IDENTITY)
    assert helper.settle(proof,owner_authorized=True) == "CONFIRMED"
    now = s.value.provider.store.document
    assert {key for key in before["records"] if before["records"][key] != now["records"][key]} == {"global.summary"}
    assert context.effects.receipt(Action.IDENTITY) == {**old,"outcome":"NOT_DISPATCHED"}
    assert helper.settle(proof,owner_authorized=True) == "CONFIRMED"
    assert not updates(s) and s.value.setup.store.read() == original
    if fallback:
        assert context.checkpoint.read().grant.epoch == 2
        with pytest.raises(ConfigurationError,match="OWNER_SUPERSEDED"):
            s.roots.resume_revoked(proof,owner_authorized=True)


def test_confirmed_non_dispatch_allows_separately_armed_same_owner_same_identity_move_once():
    s,proof = revoked(); original = s.value.setup.store.read()
    with pytest.raises(ConfigurationError,match="ROOT_EVIDENCE"):
        s.roots.resume_revoked(proof,owner_authorized=True)
    assert ProvenNoDispatchSettlement(s.value.context).settle(proof,owner_authorized=True) == "CONFIRMED"
    with pytest.raises(ConfigurationError,match="OWNER_REQUIRED"):
        s.roots.resume_revoked(proof)
    assert s.roots.resume_revoked(proof,owner_authorized=True) == "READY" and not updates(s)
    with pytest.raises(ConfigurationError):
        s.roots.require_revocation(proof)
    assert s.roots.advance(owner_authorized=True) == "CONFIRMED"
    assert len(updates(s)) == 1 and s.value.effects.receipt(Action.IDENTITY)["outcome"] == "COMPLETE"
    assert s.value.effects.receipt(Action.IDENTITY)["operation_id"] == proof.operation_id
    assert s.value.setup.store.read() == original


def test_same_prepared_live_sender_is_fenced_even_if_tombstone_and_cursor_resume_finish_inside_start():
    s = system(); s.roots.begin(owner_authorized=True)
    start = s.value.effects.start; seen = []
    def stop_and_resolve(*args,**kwargs):
        result = start(*args,**kwargs)
        proof = s.roots.revoke_prepared(owner_authorized=True)
        assert ProvenNoDispatchSettlement(s.value.context).settle(proof,owner_authorized=True) == "CONFIRMED"
        assert s.roots.resume_revoked(proof,owner_authorized=True) == "READY"
        seen.append(proof); return result
    s.value.effects.start = stop_and_resolve
    with pytest.raises(ConfigurationError,match="ROOT_CHANGED"):
        s.roots.advance(owner_authorized=True)
    assert len(seen) == 1 and not updates(s)
    assert s.value.effects.receipt(Action.IDENTITY)["outcome"] == "NOT_DISPATCHED"
    s.value.effects.start = start
    assert s.roots.advance(owner_authorized=True) == "CONFIRMED" and len(updates(s)) == 1


@pytest.mark.parametrize("fault",["default-owner","forged","wrong-epoch","wrong-index","foreign-origin","force","clock","source","action","old-store","before-only"])
def test_missing_or_stale_native_non_dispatch_proof_never_clears_unknown_or_retries(fault):
    s,proof = revoked(); ctx = s.value.context; helper = ProvenNoDispatchSettlement(ctx)
    if fault == "forged":
        proof = replace(proof,payload_sha256="a"*64)
    elif fault == "wrong-epoch":
        proof = replace(proof,epoch=proof.epoch+1)
    elif fault == "wrong-index":
        proof = replace(proof,index=proof.index+1)
    elif fault == "foreign-origin":
        from tb4.reconfiguration_roots import DocsRootMoves
        from reconfiguration_candidate_support import private
        proof = replace(proof,_origin=DocsRootMoves(replace(s.context,store=private(29))))
    elif fault == "force":
        s.value.provider.store.document["records"]["global.force_request"].update(retention="BUSY",body={"synthetic":True})
    elif fault == "clock":
        from test_native_leadership import clock
        helper = ProvenNoDispatchSettlement(replace(ctx,clock=lambda:clock(trusted=False)))
    elif fault == "source":
        ctx.source.catalog["profiles"][0]["status"] = "REVOKED"; ctx.source.save()
    elif fault == "action":
        caps = ctx.capabilities()
        helper = ProvenNoDispatchSettlement(replace(ctx,capabilities=lambda:replace(caps,actions=frozenset({Action.SCAN}))))
    elif fault == "old-store":
        def unavailable():
            raise SettingsError("SYNTHETIC_OLD_NATIVE_PROOF_UNAVAILABLE")
        s.context.store.read = unavailable
    elif fault == "before-only":
        proof = object()
    before = copy.deepcopy(s.value.provider.store.document)
    expected = AuthorityError if fault == "force" else (ConfigurationError,SettingsError)
    with pytest.raises(expected,match="FORCE_SHAPE" if fault == "force" else None):
        helper.settle(proof,owner_authorized=fault != "default-owner")
    assert s.value.provider.store.document == before and not updates(s)
    assert ctx.effects.receipt(Action.IDENTITY)["outcome"] == "UNKNOWN"


def test_fresh_second_reader_of_same_actual_native_root_revalidates_receipt_without_sdk():
    from tb4.reconfiguration_roots import DocsRootMoves
    s,_ = revoked(); reader = DocsRootMoves(s.context); proof = reader.revocation()
    original = s.value.setup.store.read(); before = copy.deepcopy(s.value.provider.store.document)
    old = s.value.effects.receipt(Action.IDENTITY)
    assert proof._origin is reader and reader.require_revocation(proof) == proof
    assert ProvenNoDispatchSettlement(s.value.context).settle(proof,owner_authorized=True) == "CONFIRMED"
    assert {k for k,v in before["records"].items() if s.value.provider.store.document["records"][k] != v} == {"global.summary"}
    assert s.value.effects.receipt(Action.IDENTITY) == {**old,"outcome":"NOT_DISPATCHED"}
    assert not updates(s) and s.value.setup.store.read() == original


def test_possible_send_with_provider_before_metadata_remains_unknown_not_non_dispatch():
    s = system(); s.roots.begin(owner_authorized=True); s.failure[0] = "before"
    assert s.roots.advance(owner_authorized=True) == "UNKNOWN" and len(updates(s)) == 1
    with pytest.raises(ConfigurationError,match="ROOT_REVOCATION_REQUIRED"):
        s.roots.revocation()
    before = copy.deepcopy(s.value.provider.store.document)
    with pytest.raises(ConfigurationError):
        ProvenNoDispatchSettlement(s.value.context).settle(object(),owner_authorized=True)
    assert s.value.provider.store.document == before and s.roots.advance(owner_authorized=True) == "UNKNOWN"
    assert len(updates(s)) == 1


def test_ordinary_start_still_refuses_same_operation_not_dispatched_receipt():
    s,proof = revoked(); helper = ProvenNoDispatchSettlement(s.value.context)
    assert helper.settle(proof,owner_authorized=True) == "CONFIRMED"
    before = copy.deepcopy(s.value.provider.store.document)
    with pytest.raises(ConfigurationError,match="CONFIGURATION_EFFECT_UNKNOWN"):
        s.value.effects.start(s.value.context.checkpoint.read().grant,Action.IDENTITY,proof.operation_id)
    assert s.value.provider.store.document == before and not updates(s)


def test_cancel_lost_doc_receipt_inspects_same_native_intent_without_provider_move():
    s,proof = revoked(); compare = s.value.context.leadership.backend.compare_replace
    from tb4.drive.docs_authority import WriteResult
    def lost(snapshot,desired):
        compare(snapshot,desired); return WriteResult.UNKNOWN
    s.value.context.leadership.backend.compare_replace = lost
    assert ProvenNoDispatchSettlement(s.value.context).settle(proof,owner_authorized=True) == "CONFIRMED"
    assert not updates(s) and s.value.effects.receipt(Action.IDENTITY)["outcome"] == "NOT_DISPATCHED"
