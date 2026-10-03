"""Inherited exact cloud facts do not need old host/WAL or grant routing."""
import copy
from dataclasses import replace
import pytest

from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError
from tb4.private_settings import SettingsError
from tb4.reconfiguration_effects import SLOT
from tb4.reconfiguration_root_settlement import InheritedRootSettlement
from tb4.watchdog.leadership_runtime import Action
from reconfiguration_roots_support import system, TARGET
from test_reconfiguration_effects import acquire_fallback


def inherited(key="artifact.000.input", *, applied=True):
    s = system(); s.roots.begin(owner_authorized=True)
    count = list(s.roots.old.spec.artifact_keys + ("authority",)).index(key)
    for _ in range(count):
        assert s.roots.advance(owner_authorized=True) == "CONFIRMED"
    taken = []
    def take():
        taken.append(acquire_fallback(s.value))
    if applied:
        s.before[0] = take
        assert s.roots.advance(owner_authorized=True) == "APPLIED_OWNER_SUPERSEDED"
    else:
        start = s.value.effects.start
        def start_and_take(*args,**kwargs):
            result = start(*args,**kwargs); take(); return result
        s.value.effects.start = start_and_take
        with pytest.raises(ConfigurationError,match="OWNER_SUPERSEDED"):
            s.roots.advance(owner_authorized=True)
    context = taken[0][2]
    return s,context,InheritedRootSettlement(context)


@pytest.mark.parametrize("key",["artifact.000.input","artifact.000.output","authority"])
def test_new_role_settles_actual_cloud_after_witness_with_all_old_private_state_unavailable(key):
    s,context,helper = inherited(key)
    before = copy.deepcopy(s.value.provider.store.document); moves = copy.deepcopy(s.moves)
    original = s.value.setup.store.read(); profile = context.setup.store.read()
    old_entry = s.value.effects.receipt(Action.IDENTITY)
    def absent():
        raise SettingsError("SYNTHETIC_OLD_HOST_UNAVAILABLE")
    for store in (s.value.setup.store,s.context.store,s.value.context.store,s.value.context.baseline.store,
                  s.value.context.checkpoint.store,s.value.context.effects.store,
                  s.context.candidate.context.profile,s.context.candidate.context.archive,
                  s.context.candidate.context.transaction,s.context.candidate.context.resolution.store):
        store.read = absent
    proof = helper.inspect()
    assert proof.key == key and helper.settle(proof,owner_authorized=True) == "CONFIRMED"
    now = s.value.provider.store.document
    assert {k for k in before["records"] if before["records"][k] != now["records"][k]} == {SLOT}
    fact = context.effects.receipt(Action.IDENTITY)
    assert fact == {**old_entry,"outcome":"COMPLETE"}
    assert fact["epoch"] == 1 and context.checkpoint.read().grant.epoch == 2
    assert helper.settle(proof,owner_authorized=True) == "CONFIRMED"
    assert s.moves == moves and context.setup.store.read() == profile
    assert original.payload["installation_id"] != profile.payload["installation_id"]
    assert len([m for m in s.value.provider.metadata.values()
                if m.get("mimeType") == "application/vnd.google-apps.document"]) == 1


@pytest.mark.parametrize("fault",["before","missing","historical","access","foreign-op","uncovered","wrong-blueprint","wrong-catalogue","lost-role","force","clock","withdrawn","wrong-action"])
def test_unproven_or_currently_unauthorized_inherited_root_never_clears_unknown(fault):
    s,context,helper = inherited(applied=fault != "before")
    document = s.value.provider.store.document
    ref = s.roots._state()[0]["objects"][0]["id"]
    if fault == "missing":
        del s.value.provider.metadata[ref]
    elif fault == "historical":
        s.value.provider.metadata[ref]["properties"]["tb4Reconfiguration"] = "a"*64
    elif fault == "access":
        s.value.provider.metadata[TARGET]["capabilities"]["canEdit"] = False
    elif fault == "foreign-op":
        document["records"][SLOT]["body"]["tb4_effects_v1"]["entries"][Action.IDENTITY.value]["operation_id"] = "f"*64
    elif fault == "uncovered":
        document["records"][SLOT]["body"]["tb4_effects_v1"]["barrier"]["local_clear"] = False
    elif fault == "wrong-blueprint":
        document["records"]["global.commissioning"]["body"]["blueprint_sha256"] = "a"*64
    elif fault == "wrong-catalogue":
        document["records"]["target.000.catalogue"]["body"]["artifacts"]["input"]["seal"] = "a"*64
    elif fault == "lost-role":
        row = document["records"]["global.leadership"]
        row["generation"] += 1; row["body"]["epoch"] += 1
    elif fault == "force":
        document["records"]["global.force_request"].update(retention="BUSY",body={"synthetic":True})
    elif fault == "clock":
        from test_native_leadership import clock
        helper.context = replace(context,clock=lambda:clock(trusted=False))
    elif fault == "withdrawn":
        context.source.catalog["profiles"][0]["status"] = "REVOKED"; context.source.save()
    elif fault == "wrong-action":
        caps = context.capabilities()
        helper.context = replace(context,capabilities=lambda:replace(caps,actions=frozenset({Action.SCAN})))
    before = copy.deepcopy(document); moves = copy.deepcopy(s.moves)
    with pytest.raises((ConfigurationError,AuthorityError,SettingsError)):
        helper.inspect()
    assert s.value.provider.store.document == before and s.moves == moves


def test_default_owner_forged_or_another_inspector_proof_cannot_settle():
    s,context,helper = inherited(); proof = helper.inspect()
    before = copy.deepcopy(s.value.provider.store.document)
    with pytest.raises(ConfigurationError,match="OWNER_REQUIRED"):
        helper.settle(proof)
    with pytest.raises(ConfigurationError):
        helper.settle(replace(proof,object_id="synthetic-foreign"),owner_authorized=True)
    with pytest.raises(ConfigurationError,match="ROOT_EVIDENCE"):
        InheritedRootSettlement(context).settle(proof,owner_authorized=True)
    assert s.value.provider.store.document == before


def test_doc_commit_unknown_inspects_same_frozen_root_settlement_and_never_moves_again():
    s,context,helper = inherited(); proof = helper.inspect()
    compare = context.leadership.backend.compare_replace; moves = copy.deepcopy(s.moves)
    from tb4.drive.docs_authority import WriteResult
    def lost(snapshot,desired):
        compare(snapshot,desired)
        return WriteResult.UNKNOWN
    context.leadership.backend.compare_replace = lost
    assert helper.settle(proof,owner_authorized=True) == "CONFIRMED"
    assert context.effects.receipt(Action.IDENTITY)["outcome"] == "COMPLETE" and s.moves == moves
