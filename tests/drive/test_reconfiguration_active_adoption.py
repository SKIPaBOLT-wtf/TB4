"""Current ACTIVE adoption, inherited UNKNOWN availability and fresh fencing."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator

from tb4.ballpark_records import provenance, validate_receipt
from tb4.commissioning_state import Setup, DenyActivation
from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.leadership import Leadership
from tb4.private_settings import SettingsError
from tb4.reconfiguration_active_adoption import ActiveAdoption, current_admission
from tb4.reconfiguration_candidate import SCHEMA, SCHEMA_SHA256
from tb4.reconfiguration_effects import KEY, SLOT, changed_row, ledger
from tb4.watchdog.leadership_runtime import Action, Receipt, Work
from reconfiguration_active_adoption_support import system, finish, runtime
from reconfiguration_rebind_support import TARGET
from test_native_leadership import clock, tid
from tests.security.test_linux_credentials import Native as CredentialNative, Runner as CredentialRunner, TARGET as DEVICE, TRUST
from tb4.linux_credentials import LinuxKeyStore
from tb4.credential_contract import CredentialResolver, Outcome, Purpose

ERRORS = (ConfigurationError, SettingsError, AuthorityError)


def test_actual_current_role_adopts_without_former_host_wal_or_ack_and_retains_own_profile():
    s=system();doc=copy.deepcopy(s.value.provider.store.document);writes=len(s.value.provider.store.calls)
    identity=s.before.payload["installation_id"];oldnonce=s.before.payload["setup_nonce"]
    admission=finish(s);frame=s.local.profile.read();value=frame.payload
    assert s.local.checkpoint.read().grant.epoch == 2
    assert frame.revision == s.before.revision+1 and frame.previous == s.before.payload
    assert value["installation_id"] == identity and value["setup_nonce"] == oldnonce
    assert value["operations"] == s.before.payload["operations"] == {"f"*64:"CONFIRMED"}
    assert value.get("credential_image") == s.before.payload.get("credential_image")
    assert value["choices"]["network_scope"] == ["198.51.100.0/24"]
    assert value["choices"]["descriptor"]["topology"] == "ISOLATED"
    assert value["choices"]["descriptor"]["devices"][0]["interfaces"] == s.before.payload["choices"]["descriptor"]["devices"][0]["interfaces"]
    assert value["choices"]["storage"]["spec"]["root_id"] == TARGET
    assert s.context.archive.read().payload["profile"] == s.before.payload
    active=value["ballpark_publication"]["active"]
    assert active["adoption"]["provenance"] == doc["records"]["global.registry"]["body"]["provenance"]
    assert provenance(active) != active["adoption"]["provenance"]
    assert active["decision"]["at"] == s.local.clock().utc
    assert not Setup(s.local.profile).status()["settings_validated"]
    assert not s.adoption.view()["runtime_active"]
    assert s.value.provider.store.document == doc and len(s.value.provider.store.calls) == writes
    # Restart from own Main/checkpoint alone. Candidate/WAL/archive are irrelevant.
    def unavailable(*args,**kwargs):raise OSError("SYNTHETIC_OWN_ADOPTION_WAL_UNAVAILABLE")
    for store in (s.context.profile,s.context.archive,s.context.transaction):store.read=store.save=unavailable
    fresh=current_admission(s.local);assert fresh.revision()==2
    runner=runtime(s,fresh);assert runner.tick()
    seen=[];work=Work(Action.WOL,tid("new-active-adopted-work"),lambda *args:seen.append(True) or "COMPLETE")
    assert runner.perform(work)=="COMPLETE" and runner.perform(work)=="COMPLETE" and len(seen)==1
    assert fresh.revision()==2


@pytest.mark.parametrize("retention",["BUSY","UNREAD","UNKNOWN"])
def test_inherited_shared_work_does_not_require_old_peer_ack_or_change_work(retention):
    s=system();row=dict(generation=17,operation_id="a"*64,retention=retention,body={"synthetic_work":True})
    s.value.provider.store.document["records"]["target.000.work"]=copy.deepcopy(row)
    before=copy.deepcopy(s.value.provider.store.document);writes=len(s.value.provider.store.calls)
    admission=finish(s)
    assert admission.revision()==2 and s.value.provider.store.document==before
    assert len(s.value.provider.store.calls)==writes and s.value.provider.store.document["records"]["target.000.work"]==row


def test_inherited_shared_unknown_effect_never_replays_but_current_role_can_observe():
    s=system();doc=s.value.provider.store.document;old=ledger(doc["records"][SLOT])
    prior=dict(owner=doc["records"]["global.commissioning"]["body"]["bootstrap_actor"],
        epoch=1,operation_id=tid("old-unknown-active-effect"),outcome="UNKNOWN")
    old["entries"][Action.SSH.value]=prior
    doc["records"][SLOT]=changed_row(doc["records"][SLOT],old)
    before=copy.deepcopy(doc);writes=len(s.value.provider.store.calls);admission=finish(s)
    assert admission.revision()==2 and doc==before and len(s.value.provider.store.calls)==writes
    runner=runtime(s,admission);assert runner.tick()
    called=[]
    assert runner.perform(Work(Action.SSH,prior["operation_id"],lambda *args:called.append(True) or "COMPLETE"))=="UNKNOWN"
    assert not called and s.effects.receipt(Action.SSH)==prior
    assert doc["records"]["global.commissioning"]==before["records"]["global.commissioning"]


@pytest.mark.parametrize("fault",["source","permission","environment","profile","role","force","timing","barrier"])
def test_current_facts_change_refuses_main_promotion_without_remote_write_or_replay(fault):
    s=system();s.adoption.begin(owner_authorized=True)
    s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    doc=s.value.provider.store.document
    if fault=="source":s.value.source.catalog["profiles"][0]["status"]="REVOKED";s.value.source.save()
    elif fault=="permission":s.value.provider.metadata[TARGET]["capabilities"]["canEdit"]=False
    elif fault=="environment":s.checker.environment=lambda:None
    elif fault=="profile":Setup(s.local.profile).cancel()
    elif fault=="role":doc["records"]["global.leadership"]["body"]["epoch"]+=1
    elif fault=="force":
        requester=Leadership(s.local.leadership.backend,actor=s.value.flow.leader.actor,enrollment=s.local.leadership.enrollment)
        plan=requester.request_force(requester.observe(s.local.clock()),request_id=tid("force-new-adoption"),user_requested=True)
        assert requester.commit(plan,mode="START").outcome=="CONFIRMED"
    elif fault=="timing":doc["records"]["global.settings"]["body"]["timing"]["control_s"]+=1
    else:doc["records"][SLOT]["body"][KEY]["barrier"]["local_clear"]=False
    main=s.local.profile.read();cp=s.local.checkpoint.read();before=copy.deepcopy(doc);writes=len(s.value.provider.store.calls)
    with pytest.raises(ERRORS):s.adoption.advance(owner_authorized=True)
    assert s.local.profile.read()==main and s.local.checkpoint.read()==cp and doc==before and len(s.value.provider.store.calls)==writes


@pytest.mark.parametrize("fault",["setup-unknown","local-effect","clock","caps","identities"])
def test_invalid_own_local_state_never_stages_or_blocks_actual_election(fault):
    s=system();assert s.local.checkpoint.read().grant.epoch==2
    if fault=="setup-unknown":
        model=Setup(s.local.profile);model.perform_once("e"*64,lambda:None,owner_authorized=True)
    elif fault=="local-effect":
        cp=s.local.checkpoint.read();assert s.local.checkpoint.replace(cp,replace(cp,receipts=(
            Receipt(Action.SSH,tid("own-unresolved-effect"),cp.grant.epoch,"UNKNOWN"),)))
    elif fault=="clock":
        local=replace(s.local,clock=lambda:replace(s.local.clock(),wall_trusted=False))
        s.adoption=ActiveAdoption(replace(s.context,local=local))
    elif fault=="caps":
        local=replace(s.local,capabilities=lambda:replace(s.local.capabilities(),coordinate=False))
        s.adoption=ActiveAdoption(replace(s.context,local=local))
    else:
        model=Setup(s.local.profile);descriptor=model.private_choices()["descriptor"];descriptor["devices"][0]["alias"]="synthetic-other"
        model.choose({"descriptor":descriptor})
    main=s.local.profile.read();cp=s.local.checkpoint.read();writes=len(s.value.provider.store.calls)
    with pytest.raises(ERRORS):s.adoption.begin(owner_authorized=True)
    assert s.local.profile.read()==main and s.local.checkpoint.read()==cp
    assert s.context.transaction.read() is None and len(s.value.provider.store.calls)==writes


def test_selected_own_credential_is_preserved_and_fresh_revocation_refuses_promotion():
    s=system();native=CredentialNative();runner=CredentialRunner(native)
    store=LinuxKeyStore(s.before.payload["installation_id"],native=native,runner=runner,clock=lambda:100)
    selected=store.select(path="/synthetic/private/key",target_id=DEVICE,target_trust=TRUST,
        purposes=frozenset({Purpose.FETCHER_STATUS}),expires_at=200,access_mode="existing_key",
        launch_mode="headless",owner_authorized=True)
    resolver=CredentialResolver(store.installation_id,store,clock=lambda:100)
    handle=resolver.enroll(target_id=DEVICE,target_trust=TRUST,store_locator=selected,
        purposes=frozenset({Purpose.FETCHER_STATUS}),expires_at=200,owner_authorized=True)
    Setup(s.local.profile).persist_credentials(store,resolver,[dict(handle=handle,target_id=DEVICE,
        target_trust=TRUST,purposes=[Purpose.FETCHER_STATUS.value])])
    before=s.local.profile.read();s.checker.credentials=resolver
    s.adoption.begin(owner_authorized=True)
    assert s.context.profile.read().payload["credential_image"]==before.payload["credential_image"]
    assert s.context.profile.read().payload["choices"]["credentials"]==before.payload["choices"]["credentials"]
    s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    resolver.revoke(handle,owner_authorized=True)
    with pytest.raises(SettingsError,match="CREDENTIAL_UNAVAILABLE"):s.adoption.advance(owner_authorized=True)
    assert s.local.profile.read()==before and runner.calls==0 and native.held==0


@pytest.mark.parametrize("fault",["stage","takeover"])
def test_actual_change_during_first_run_never_promotes_main(fault):
    s=system();s.adoption.begin(owner_authorized=True)
    before=s.local.profile.read();probe=s.checker.environment;seen=[]
    def late():
        if not seen:
            seen.append(True)
            if fault=="stage":Setup(s.context.profile).choose({"network_scope":["203.0.113.0/24"]})
            else:s.value.provider.store.document["records"]["global.leadership"]["body"]["epoch"]+=1
        return probe()
    s.checker.environment=late
    with pytest.raises(ERRORS):s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    assert seen and s.local.profile.read()==before and s.context.transaction.read().payload["phase"]=="STAGED"


def test_closed_receipt_named_schema_owner_alias_and_default_activation_are_not_saved_grants():
    s=system()
    with pytest.raises(ConfigurationError,match="OWNER_REQUIRED"):s.adoption.begin()
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):ActiveAdoption(replace(s.context,profile=s.local.profile))
    with pytest.raises(ConfigurationError,match="ACTIVE_ADOPTION_CONTEXT"):ActiveAdoption(replace(s.context,local=object()))
    s.adoption.begin(owner_authorized=True)
    raw=(Path(__file__).parents[2]/SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SCHEMA_SHA256
    schema=json.loads(raw);validator=Draft202012Validator(schema["$defs"]["activeAdoption"])
    assert validator.is_valid(s.context.transaction.read().payload)
    s.adoption.prepare(owner_authorized=True,decided_at=s.local.clock().utc)
    assert validator.is_valid(s.context.transaction.read().payload)
    s.adoption.advance(owner_authorized=True);active=s.local.profile.read().payload["ballpark_publication"]["active"]
    choices=s.local.profile.read().payload["choices"]
    for mutation in ("extra","authority","provenance","configuration"):
        bad=copy.deepcopy(active)
        if mutation=="extra":bad["adoption"]["foreign"]="SYNTHETIC"
        elif mutation=="authority":bad["adoption"]["authority"]["binding"]["domain_id"]="00000000-0000-0000-0000-000000000001"
        elif mutation=="provenance":bad["adoption"]["provenance"]["decision_id"]="invalid"
        else:bad["adoption"]["configuration"]["phase"]="MAINTENANCE"
        with pytest.raises(ValueError):validate_receipt(bad,choices)
    assert not Setup(s.local.profile).activate(current_admission(s.local).context.checker,DenyActivation())["runtime_active"]
