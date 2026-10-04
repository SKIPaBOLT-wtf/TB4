"""Actual post-root first-run/current-role boundaries, no activation or replay."""
from dataclasses import replace
import copy
import hashlib
import json
from pathlib import Path

import pytest

from tb4.commissioning_state import Setup
from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError
from tb4.private_settings import SettingsError
from tb4.reconfiguration_candidate import DERIVED,SCHEMA
from tb4.reconfiguration_post_root import PostRootCandidate,SCHEMA_SHA256
from tb4.watchdog.leadership_runtime import Action
from reconfiguration_candidate_support import private
from reconfiguration_post_root_support import system,candidate_for,checker_for
from reconfiguration_rebind_support import fallback,system as rebind_system,TARGET
from test_native_leadership import clock


def unchanged(s, original, document, writes):
    assert s.rebind.value.setup.store.read() == original
    assert s.rebind.value.provider.store.document == document
    assert len(s.rebind.value.provider.store.calls) == writes
    assert len(s.rebind.moves) == 3


def test_actual_target_first_run_archive_history_and_original_authority_are_preserved():
    s=system();v=s.rebind.value;original=v.setup.store.read();doc=copy.deepcopy(v.provider.store.document)
    writes=len(v.provider.store.calls)
    assert s.candidate.begin(owner_authorized=True)["phase"] == "STAGED"
    archive=s.context.archive.read()
    assert archive.revision == 1 and archive.previous is None and archive.payload["profile"] == original.payload
    payload=s.context.profile.read().payload
    assert payload["choices"]["storage"]["spec"]["root_id"] == TARGET
    assert all(payload[k] == original.payload[k] for k in ("installation_id","setup_nonce","operations"))
    assert not (set(payload) & DERIVED)
    assert s.candidate.review(s.checker)["settings_validated"]
    proof=s.candidate.require_validated(s.checker)
    assert s.candidate.require_current(proof,s.checker) == proof
    assert not s.candidate.view()["runtime_active"] and not s.candidate.view()["automatic_replay"]
    restarted=PostRootCandidate(s.context)
    assert not restarted.view()["settings_validated"]
    with pytest.raises(ConfigurationError):restarted.require_current(proof,s.checker)
    assert restarted.require_validated(s.checker).revision == s.context.profile.read().revision
    unchanged(s,original,doc,writes)


@pytest.mark.parametrize("fault",["source","permission","clock","caps","election","work","force","profile","receipt"])
def test_actual_fresh_guards_refuse_saved_readiness_without_remote_write_or_original_reset(fault):
    s=system();v=s.rebind.value;s.candidate.begin(owner_authorized=True)
    proof=s.candidate.require_validated(s.checker);writes=len(v.provider.store.calls)
    original=v.setup.store.read();before=s.context.profile.read()
    if fault=="source":v.source.catalog["profiles"][0]["status"]="REVOKED";v.source.save()
    elif fault=="permission":v.provider.metadata[TARGET]["capabilities"]["canEdit"]=False
    elif fault=="clock":s.rebind.rebind.ctx=replace(s.rebind.rebind.ctx,clock=lambda:clock(trusted=False))
    elif fault=="caps":
        ctx=s.rebind.rebind.ctx;s.rebind.rebind.ctx=replace(ctx,capabilities=lambda:replace(
            ctx.capabilities(),actions=frozenset({Action.SCAN})))
    elif fault=="election":
        cp=v.checkpoint.read();plan=v.context.leadership.renew(v.context.leadership.observe(v.context.clock()),
            cp.grant,transition="e"*64)
        assert v.checkpoint.replace(cp,replace(cp,election=plan))
    elif fault=="work":v.provider.store.document["records"]["target.000.status"]["body"]={"synthetic":True}
    elif fault=="force":v.provider.store.document["records"]["global.force_request"].update(
        retention="BUSY",body={"synthetic":True})
    elif fault=="profile":v.setup.choose({"network_scope":v.setup.private_choices()["network_scope"]})
    else:v.provider.store.document["records"]["global.commissioning"]["body"]["reconfiguration"]["work_sha256"]="f"*64
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        s.candidate.require_current(proof,s.checker)
    assert s.context.profile.read() == before and len(v.provider.store.calls) == writes
    if fault!="profile":assert v.setup.store.read() == original


def test_actual_staged_topology_lost_credential_and_forged_proof_require_current_first_run():
    s=system();v=s.rebind.value;original=v.setup.store.read();doc=copy.deepcopy(v.provider.store.document)
    writes=len(v.provider.store.calls);s.candidate.begin(owner_authorized=True)
    proof=s.candidate.require_validated(s.checker)
    s.candidate.choose({"network_scope":["192.0.2.0/24"]},owner_authorized=True)
    assert not s.candidate.view()["settings_validated"]
    with pytest.raises(ConfigurationError):s.candidate.require_current(proof,s.checker)
    selected=[dict(handle="cr_"+"a"*32,target_id="30000000-0000-4000-8000-000000000001",
        target_trust="b"*64,purposes=["FETCHER_STATUS"])]
    s.candidate.choose({"credentials":selected},owner_authorized=True)
    assert not s.candidate.review(s.checker)["settings_validated"]
    assert Setup(s.context.profile).status()["reason"] == "CREDENTIAL_UNAVAILABLE"
    s.candidate.choose({"credentials":[]},owner_authorized=True)
    proof=s.candidate.require_validated(s.checker)
    with pytest.raises(ConfigurationError):
        s.candidate.require_current(replace(proof,epoch=proof.epoch+1),s.checker)
    with pytest.raises(ConfigurationError):
        s.candidate.choose({"storage":original.payload["choices"]["storage"]},owner_authorized=True)
    unchanged(s,original,doc,writes)


def test_actual_fresh_fallback_first_run_needs_no_former_profile_candidate_or_wal_ack():
    s=system();s.candidate.begin(owner_authorized=True);s.candidate.require_validated(s.checker)
    current=fallback(s.rebind);ctx=current.ctx;writes=len(s.rebind.value.provider.store.calls)
    for store in (s.rebind.value.setup.store,s.rebind.value.checkpoint.store,s.rebind.value.effects.store,
                  s.rebind.context.store,s.rebind.roots.context.store,s.context.profile,s.context.archive,s.context.transaction):
        store.read=lambda:(_ for _ in ()).throw(SettingsError("SYNTHETIC_FORMER_HOST_UNAVAILABLE"))
    context,candidate=candidate_for(current)
    assert candidate.begin(owner_authorized=True)["phase"] == "STAGED"
    proof=candidate.require_validated(checker_for(current))
    assert proof.epoch == 2 and context.profile.read().payload["installation_id"] == ctx.setup.installation_id
    assert len(s.rebind.value.provider.store.calls) == writes and len(s.rebind.moves) == 3
    assert not candidate.view()["runtime_active"]


@pytest.mark.parametrize("phase",["validate-current","validate-new"])
def test_actual_candidate_change_during_first_run_probe_cannot_return_a_stale_or_unvalidated_proof(phase):
    s=system();v=s.rebind.value;s.candidate.begin(owner_authorized=True)
    original=v.setup.store.read();doc=copy.deepcopy(v.provider.store.document);writes=len(v.provider.store.calls)
    proof=s.candidate.require_validated(s.checker) if phase=="validate-current" else None
    environment=s.checker.environment;calls=[]
    def changed():
        calls.append(True)
        if len(calls)==(1 if phase=="validate-current" else 2):
            s.candidate.choose({"network_scope":["192.0.2.0/24"]},owner_authorized=True)
        return environment()
    s.checker.environment=changed
    with pytest.raises((ConfigurationError,SettingsError)):
        s.candidate.require_current(proof,s.checker) if proof is not None else s.candidate.require_validated(s.checker)
    assert s.context.profile.read().payload["choices"]["network_scope"] == ["192.0.2.0/24"]
    assert not s.candidate.view()["settings_validated"]
    unchanged(s,original,doc,writes)


def test_actual_partial_or_unrebound_storage_and_aliases_are_never_staging_grants():
    s=rebind_system();context,candidate=candidate_for(s.rebind)
    with pytest.raises((ConfigurationError,AuthorityError,SettingsError)):candidate.begin(owner_authorized=True)
    assert context.transaction.read() is None and context.archive.read() is None and context.profile.read() is None
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
        PostRootCandidate(replace(context,profile=s.value.effects.store))


def test_named_schema_preserves_legacy_top_level_and_current_pin_size():
    from jsonschema import Draft202012Validator
    s=system();s.candidate.begin(owner_authorized=True)
    raw=(Path(__file__).parents[2]/SCHEMA).read_bytes();schema=json.loads(raw)
    assert hashlib.sha256(raw).hexdigest() == SCHEMA_SHA256
    frame=s.context.transaction.read().payload
    assert Draft202012Validator(schema["$defs"]["postRootCandidate"]).is_valid(frame)
    assert Draft202012Validator(schema["$defs"]["postRootArchive"]).is_valid(s.context.archive.read().payload)
    assert not Draft202012Validator(schema["$defs"]["postRootCandidate"]).is_valid({**frame,"foreign":True})
    assert not Draft202012Validator(schema).is_valid(frame)
    assert Draft202012Validator(schema).is_valid(s.rebind.candidate.context.transaction.read().payload)
    assert len(frame["pin"]["files"]) <= 17
