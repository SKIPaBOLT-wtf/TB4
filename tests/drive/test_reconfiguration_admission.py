"""Current-source/current-role admission, actual runtime effect guards and no replay."""
import copy
from dataclasses import replace
import pytest

from tb4.commissioning_state import Setup, DenyActivation
from tb4.configuration_contract import ConfigurationError, configuration
from tb4.credential_contract import CredentialResolver, Outcome, Purpose
from tb4.drive.authority_transaction import OwnerGuard, RecordMutation
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.leadership import Leadership
from tb4.private_settings import SettingsError
from tb4.reconfiguration_admission import ConfigurationAdmission
from tb4.reconfiguration_effects import KEY, SLOT
from tb4.watchdog.leadership_runtime import Action, NativeWatchdogContext, NativeWatchdogRuntime, Receipt, Work
from reconfiguration_admission_support import system
from reconfiguration_rebind_support import TARGET
from test_reconfiguration_effects import acquire_fallback
from test_native_leadership import ACTORS, clock, tid
from tests.security.test_credential_contract import FixtureStore, TARGET as DEVICE, TRUST


def runtime(s):
    v=s.value
    ctx=NativeWatchdogContext(s.context.leadership, v.checkpoint, s.context.capabilities,
        s.context.clock, lambda:None, configuration_revision=s.admission.revision, effects=v.effects)
    return NativeWatchdogRuntime(ctx)


def test_actual_release_changes_only_native_reservation_and_ordinary_runtime_uses_fresh_admission():
    s=system();v=s.value
    cp=v.checkpoint.read();native=v.checkpoint.store.read();profile=v.setup.store.read()
    document=copy.deepcopy(v.provider.store.document);writes=len(v.provider.store.calls)
    with pytest.raises(ConfigurationError,match="CONFIGURATION_MAINTENANCE"):s.admission.revision()
    revision=s.admission.release(owner_authorized=True)
    assert revision==configuration(document)["revision"]
    assert v.checkpoint.read()==replace(cp,maintenance=None)
    assert v.checkpoint.store.read().revision==native.revision+1 and v.checkpoint.store.read().previous==native.payload
    assert v.setup.store.read()==profile and v.provider.store.document==document and len(v.provider.store.calls)==writes
    assert not s.admission.status()["runtime_active"]
    assert not Setup(v.setup.store).status()["settings_validated"]
    runner=runtime(s);assert runner.tick()
    called=[];work=Work(Action.WOL,tid("admitted-new-work"),lambda *args:called.append(args) or "COMPLETE")
    assert runner.perform(work)=="COMPLETE" and len(called)==1
    assert runner.perform(work)=="COMPLETE" and len(called)==1
    assert v.setup.store.read()==profile and profile.payload["operations"]==profile.previous["operations"]
    assert v.checkpoint.read().maintenance is None and s.admission.revision()==revision


def test_actual_restarted_admission_allows_new_work_without_old_frozen_transaction_proof():
    s=system();s.admission.release(owner_authorized=True)
    s.admission=ConfigurationAdmission(s.context);runner=runtime(s);assert runner.tick()
    doc=s.value.provider.store.document
    doc["records"]["target.000.work"]=dict(generation=17,operation_id="a"*64,retention="BUSY",body={"synthetic_work":True})
    called=[];work=Work(Action.SSH,tid("new-unknown-work"),lambda *args:called.append(True) or "UNKNOWN")
    assert runner.perform(work)=="UNKNOWN" and len(called)==1
    assert s.admission.revision()==configuration(doc)["revision"]
    assert runner.perform(work)=="UNKNOWN" and len(called)==1
    # Historical publication/profile-promotion proof must not be reused after
    # legitimate work/effect mutations; current admission uses fresh facts.
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):s.promotion.promotion.inspect(s.checker)
    assert doc["records"]["target.000.work"]["generation"]==17


@pytest.mark.parametrize("fault",["source","permission","clock","caps","profile","timing","maintenance",
                                 "barrier","shared-unknown","local-unknown","local-mutation","environment"])
def test_actual_changed_admission_facts_refuse_release_without_reset_or_remote_write(fault):
    s=system();v=s.value;doc=v.provider.store.document
    if fault=="source":v.source.catalog["profiles"][0]["status"]="REVOKED";v.source.save()
    elif fault=="permission":v.provider.metadata[TARGET]["capabilities"]["canEdit"]=False
    elif fault=="clock":s.admission=ConfigurationAdmission(replace(s.context,clock=lambda:replace(clock(220),wall_trusted=False)))
    elif fault=="caps":v.caps[0]=replace(v.caps[0],coordinate=False)
    elif fault=="profile":Setup(v.setup.store).cancel()
    elif fault=="timing":doc["records"]["global.settings"]["body"]["timing"]["control_s"]+=1
    elif fault=="maintenance":doc["records"]["global.settings"]["body"]["configuration"]["phase"]="MAINTENANCE"
    elif fault=="barrier":doc["records"][SLOT]["body"][KEY]["barrier"]["local_clear"]=False
    elif fault=="shared-unknown":
        doc["records"]["target.000.work"]=dict(generation=18,operation_id="b"*64,retention="UNKNOWN",body={"synthetic":True})
    elif fault=="local-unknown":
        cp=v.checkpoint.read();assert v.checkpoint.replace(cp,replace(cp,receipts=cp.receipts+(
            Receipt(Action.SSH,tid("local-unsettled"),cp.grant.epoch,"UNKNOWN"),)))
    elif fault=="local-mutation":
        cp=v.checkpoint.read();row=dict(generation=1,operation_id="b"*64,retention="RETAINED",body={"synthetic":True})
        plan=RecordMutation.prepare(v.flow.leader.backend.read(),owner=OwnerGuard(cp.grant.owner,cp.grant.epoch),
                                    changes={"target.000.work":row},protect={"global.settings"})
        assert v.checkpoint.replace(cp,replace(cp,mutation=plan))
    else:s.checker.environment=lambda:None
    cp=v.checkpoint.read();profile=v.setup.store.read();writes=len(v.provider.store.calls);before=copy.deepcopy(doc)
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):s.admission.release(owner_authorized=True)
    assert v.checkpoint.read()==cp and cp.maintenance is not None
    assert v.setup.store.read()==profile and doc==before and len(v.provider.store.calls)==writes


def test_actual_first_cas_fallback_is_immediate_and_old_promoted_profile_cannot_admit():
    s=system();v=s.value;cp=v.checkpoint.read();_,_,fallback=acquire_fallback(v)
    assert fallback.checkpoint.read().grant.epoch==2 and v.provider.store.document["records"]["global.leadership"]["body"]["epoch"]==2
    writes=len(v.provider.store.calls)
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):s.admission.release(owner_authorized=True)
    assert v.checkpoint.read()==cp and len(v.provider.store.calls)==writes


def test_actual_user_force_request_flag_fences_incumbent_before_claim_without_ack():
    s=system();v=s.value;leader=s.context.leadership
    requester=Leadership(leader.backend,actor=ACTORS[1],enrollment=leader.enrollment)
    plan=requester.request_force(requester.observe(clock(220)),request_id=tid("force-admission"),user_requested=True)
    assert requester.commit(plan,mode="START").outcome=="CONFIRMED"
    assert v.provider.store.document["records"]["global.leadership"]["body"]["owner"]==leader.actor
    cp=v.checkpoint.read();writes=len(v.provider.store.calls)
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):s.admission.release(owner_authorized=True)
    assert v.checkpoint.read()==cp and len(v.provider.store.calls)==writes


def test_actual_credential_revocation_refuses_release_without_secret_use():
    stores=[]
    def prepare(s):
        store=FixtureStore(s.value.setup.installation_id);resolver=CredentialResolver(store.installation_id,store,clock=lambda:store.now)
        handle=resolver.enroll(target_id=DEVICE,target_trust=TRUST,store_locator="synthetic-admission-slot",
            purposes=frozenset({Purpose.FETCHER_STATUS}),expires_at=200,owner_authorized=True)
        s.post_root.candidate.choose({"credentials":[dict(handle=handle,target_id=DEVICE,target_trust=TRUST,
            purposes=[Purpose.FETCHER_STATUS.value])]},owner_authorized=True)
        s.checker.credentials=resolver;stores.append(store)
    s=system(prepare=prepare);stores[0].state=Outcome.REVOKED
    cp=s.value.checkpoint.read();writes=len(s.value.provider.store.calls)
    with pytest.raises(SettingsError,match="CREDENTIAL_UNAVAILABLE"):s.admission.release(owner_authorized=True)
    assert stores[0].executions==0 and s.value.checkpoint.read()==cp and len(s.value.provider.store.calls)==writes


@pytest.mark.parametrize("fault",["profile","force"])
def test_actual_late_first_run_changes_cannot_clear_native_reservation(fault):
    s=system();v=s.value;original=s.checker.environment;changed=[];cp=v.checkpoint.read()
    def late():
        if not changed:
            changed.append(True)
            if fault=="profile":Setup(v.setup.store).choose({"credentials":[]})
            else:acquire_fallback(v)
        return original()
    s.checker.environment=late
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):s.admission.release(owner_authorized=True)
    assert changed and v.checkpoint.read()==cp


def test_typed_ports_alias_owner_confirmation_and_saved_ready_never_replace_current_proof():
    s=system()
    with pytest.raises(ConfigurationError,match="OWNER_REQUIRED"):s.admission.release()
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
        ConfigurationAdmission(replace(s.context,profile=s.value.checkpoint.store))
    with pytest.raises(ConfigurationError,match="ADMISSION_CONTEXT"):
        ConfigurationAdmission(replace(s.context,checker=object()))
    # The installed/default activation port remains independently closed.
    model=Setup(s.value.setup.store)
    assert not model.activate(s.checker,DenyActivation())["runtime_active"]
    s.value.source.catalog["profiles"][0]["status"]="REVOKED";s.value.source.save()
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):s.admission.release(owner_authorized=True)
