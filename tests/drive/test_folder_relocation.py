"""Actual same-filesystem native syscall, locked SQL authority and crash/fallback."""
from contextlib import contextmanager
from dataclasses import replace
import copy
import os
import sys

import pytest

from tb4.commissioning_checks import CommissionedStorage
from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError,WriteResult,validated
from tb4.drive.folder_authority import DB,FolderStore,identity
from tb4.private_settings import SettingsError
from tb4.reconfiguration_effects import SLOT,ledger,changed_row,EffectMutation
from tb4.reconfiguration_folder import FolderRelocation,FolderAppliedSettlement
from tb4.drive.authority_transaction import OwnerGuard
from tb4.watchdog.leadership_runtime import Action
from tests.drive.test_folder_commissioning import context  # noqa: F401
from tests.drive.folder_relocation_support import system,takeover,old_stores_unavailable
from tests.drive.test_folder_mapping import inventory
from tests.drive.test_native_leadership import ACTORS,ENROLLMENT,clock,tid

pytestmark=pytest.mark.skipif(sys.platform!="linux",reason="actual native Linux no-replace folder transaction")


@pytest.fixture
def value(context,tmp_path):return system(context,tmp_path)


@pytest.mark.parametrize("unicode",[False,True])
def test_actual_first_run_current_role_one_syscall_same_inodes_used_bytes_and_persistent_authority(context,tmp_path,monkeypatch,unicode):
    s=system(context,tmp_path,unicode=unicode);v=s.value
    artifact=v.port.root/v.port.prepare(v.spec.artifact_keys[0],v.spec.operation(v.spec.artifact_keys[0])).object_id
    artifact.write_bytes(b"synthetic already used artifact")
    files=inventory(v);profile=v.setup.store.read();snapshot=s.ctx.leadership.backend.read();before=snapshot.document()
    backend=s.ctx.leadership.backend;calls=[];run=s.native.run
    def actual(*args):
        calls.append(args)
        # Existing actual inode lock excludes both an ordinary reader and writer.
        config=v.port._config();store=FolderStore(config)
        with pytest.raises(AuthorityError):store.read()
        assert store.compare_replace(snapshot.revision,snapshot.raw) is WriteResult.UNAVAILABLE
        return run(*args)
    monkeypatch.setattr(s.native,"run",actual)
    assert s.relocation.begin(owner_authorized=True)=="PREPARED"
    assert s.candidate.view()["settings_validated"]
    assert s.relocation.advance(owner_authorized=True)=="MOVED"
    assert len(calls)==1 and calls[0][0]==v.port.root and calls[0][1]==v.target
    after=backend.read().document()
    assert {k:x for k,x in before["records"].items() if k!=SLOT}=={k:x for k,x in after["records"].items() if k!=SLOT}
    assert ledger(after["records"][SLOT])["entries"]["IDENTITY"]["outcome"]=="COMPLETE"
    assert v.setup.store.read()==profile and not v.port.root.exists()
    moved={p.name:(identity(p),os.getxattr(p,"user.tb4.commissioning") if p.name!=DB+"-journal" else None,
        p.read_bytes() if p.name not in {DB,DB+"-journal"} else None) for p in v.target.iterdir()}
    assert moved==files and CommissionedStorage(s.mapped).verify(v.setup.private_choices()["storage"])
    assert s.relocation.advance(owner_authorized=True)=="MOVED" and len(calls)==1


@pytest.mark.parametrize("when",["before","after","fsync"])
def test_ambiguous_syscall_or_durability_failure_never_resends_and_preserves_original_unknown(value,monkeypatch,when):
    s=value;v=s.value;run=s.native.run;calls=[]
    def cut(*args):
        calls.append(args)
        if when=="before":raise TimeoutError("SYNTHETIC_BEFORE_SYSCALL")
        if when=="fsync":
            with monkeypatch.context() as part:
                part.setattr(os,"fsync",lambda *_:(_ for _ in ()).throw(OSError("SYNTHETIC_DIRECTORY_SYNC")))
                run(*args)
        else:run(*args)
        raise TimeoutError("SYNTHETIC_AFTER_SYSCALL")
    monkeypatch.setattr(s.native,"run",cut)
    s.relocation.begin(owner_authorized=True)
    assert s.relocation.advance(owner_authorized=True)=="UNKNOWN"
    entry=s.ctx.effects.receipt(Action.IDENTITY)
    assert entry["outcome"]=="UNKNOWN" and s.relocation._state()[0]["dispatch"]=="INVOKING"
    assert s.relocation.advance(owner_authorized=True)==("UNKNOWN" if when=="before" else "MOVED")
    assert len(calls)==1 and v.port.root.exists()==(when=="before")


def test_kernel_no_replace_rejects_destination_created_at_the_actual_syscall(value,monkeypatch):
    s=value;v=s.value;call=s.native._call;seen=[]
    def race(*args):
        v.target.mkdir(mode=0o700);(v.target/"retained-foreign").write_bytes(b"synthetic foreign destination")
        seen.append(args);return call(*args)
    monkeypatch.setattr(s.native,"_call",race)
    s.relocation.begin(owner_authorized=True)
    assert s.relocation.advance(owner_authorized=True)=="UNKNOWN"
    assert len(seen)==1 and v.port.root.exists() and (v.target/"retained-foreign").read_bytes()==b"synthetic foreign destination"
    with pytest.raises(AuthorityError,match="HELPER_UNAVAILABLE"):
        s.relocation.advance(owner_authorized=True)
    # The protected mapped helper rejects contradictory roots. Read the exact
    # original authority inode directly to verify the retained UNKNOWN fact.
    _,raw=FolderStore(v.port._config()).read()
    receipt=ledger(validated(raw,s.ctx.leadership.backend.binding)["records"][SLOT])["entries"][Action.IDENTITY.value]
    assert len(seen)==1 and receipt["outcome"]=="UNKNOWN"


@pytest.mark.parametrize("where",["begin","invoking","applied","settled"])
def test_actual_native_pending_cut_recovery_inspects_exact_frame_and_never_repeats(value,monkeypatch,where):
    s=value;store=s.relocation.context.store;original=store.native.locked;calls=[];run=s.native.run
    monkeypatch.setattr(s.native,"run",lambda *a:(calls.append(a),run(*a))[1])
    @contextmanager
    def cut():
        with original() as port:
            class Proxy:
                def __getattr__(self,name):return getattr(port,name)
                def promote(self):
                    pending=store._decode(port.read("settings.pending"),port.binding).payload
                    selected=(pending["dispatch"]=="PREPARED" if where=="begin" else
                        pending["dispatch"]=="INVOKING" and pending["phase"]=="ARMED" if where=="invoking" else
                        pending["phase"]==where.upper())
                    if selected:raise OSError("SYNTHETIC_FOLDER_NATIVE_PROMOTION")
                    return port.promote()
            yield Proxy()
    if where!="begin":s.relocation.begin(owner_authorized=True)
    monkeypatch.setattr(store.native,"locked",cut)
    with pytest.raises((SettingsError,ConfigurationError,OSError)):
        s.relocation.begin(owner_authorized=True) if where=="begin" else s.relocation.advance(owner_authorized=True)
    monkeypatch.setattr(store.native,"locked",original)
    with pytest.raises(SettingsError):store.read()
    before=len(calls)
    assert s.relocation.recover_local(owner_authorized=True)=="INSPECT_REQUIRED"
    result=s.relocation.inspect()
    assert result in {"PREPARED","UNKNOWN","MOVED"} and len(calls)==before
    if where=="invoking":assert result=="UNKNOWN" and not calls
    if where in {"applied","settled"}:assert result=="MOVED" and len(calls)==1


@pytest.mark.parametrize("fault",["owner","source","profile","candidate","force","clock","caps","work","mapping"])
def test_changed_actual_preconditions_refuse_before_any_syscall(value,monkeypatch,fault):
    s=value;v=s.value;s.relocation.begin(owner_authorized=True);calls=[]
    monkeypatch.setattr(s.native,"run",lambda *a:calls.append(a))
    if fault=="source":v.source.fail_resolve=True
    elif fault=="profile":v.setup.choose({"network_scope":v.setup.private_choices()["network_scope"]})
    elif fault=="candidate":s.candidate.choose({"network_scope":["198.51.100.0/24"]},owner_authorized=True)
    elif fault=="clock":object.__setattr__(s.ctx,"clock",lambda:None)
    elif fault=="caps":object.__setattr__(s.ctx,"capabilities",lambda:None)
    elif fault=="force":
        from tb4.drive.leadership import Leadership
        peer=Leadership(s.ctx.leadership.backend,actor=ACTORS[1],enrollment=ENROLLMENT)
        plan=peer.request_force(peer.observe(clock(220)),request_id=tid("folder-force"),user_requested=True)
        assert peer.commit(plan,mode="START").outcome=="CONFIRMED"
    elif fault=="work":
        snap=s.ctx.leadership.backend.read();doc=snap.document()
        doc["records"]["target.000.work"].update(generation=1,operation_id="b"*64,retention="UNREAD")
        assert s.ctx.leadership.backend.compare_replace(snap,doc)==WriteResult.ACCEPTED
    elif fault=="mapping":
        current=v.mapping.store.read();v.mapping.store.save(current.payload,expected_revision=1)
    with pytest.raises((AuthorityError,SettingsError,ConfigurationError)):
        s.relocation.advance(owner_authorized=fault!="owner")
    assert not calls and v.port.root.exists() and not v.target.exists()


@pytest.mark.parametrize("after",[False,True])
def test_actual_stale_first_cas_takeover_needs_no_old_host_and_settles_only_exact_after(value,monkeypatch,after):
    s=value;v=s.value;run=s.native.run;calls=[]
    def ambiguous(*args):
        calls.append(args)
        if after:run(*args)
        raise TimeoutError("SYNTHETIC_REPLY_LOST")
    monkeypatch.setattr(s.native,"run",ambiguous)
    s.relocation.begin(owner_authorized=True)
    assert s.relocation.advance(owner_authorized=True)=="UNKNOWN"
    old=s.ctx.effects.receipt(Action.IDENTITY)
    ctx=takeover(s)
    # Old native profile/WAL/candidate evidence are unavailable, mapping facts
    # are server-local shared lookup. Role acquisition already succeeded.
    old_stores_unavailable(s,monkeypatch)
    settle=FolderAppliedSettlement(ctx,v.mapping)
    if after:
        assert settle.settle(owner_authorized=True)=="CONFIRMED"
        receipt=ctx.effects.receipt(Action.IDENTITY)
        assert receipt=={**old,"outcome":"COMPLETE"} and receipt["epoch"]<ctx.checkpoint.read().grant.epoch
        assert settle.settle(owner_authorized=True)=="CONFIRMED"
    else:
        with pytest.raises(ConfigurationError,match="AFTER_REQUIRED"):
            settle.settle(owner_authorized=True)
        assert ctx.effects.receipt(Action.IDENTITY)==old
    assert len(calls)==1 and ctx.leadership.backend.read().document()["records"]["global.leadership"]["body"]["owner"]==ctx.setup.installation_id


def test_force_arriving_after_preflight_is_refused_inside_the_actual_database_lock(value,monkeypatch):
    s=value;v=s.value;original=FolderStore.connection;entered=[False];calls=[];refusals=[]
    from tb4.drive.leadership import Leadership
    peer=Leadership(s.ctx.leadership.backend,actor=ACTORS[1],enrollment=ENROLLMENT)
    @contextmanager
    def raced(store):
        if store.config.root==v.port.root and not entered[0]:
            # A live native invocation holds its lock. Trigger at the one
            # direct SQL connection after its native INVOKING save.
            if getattr(raced,"armed",False):
                entered[0]=True
                plan=peer.request_force(peer.observe(clock(220)),request_id=tid("last-folder-force"),user_requested=True)
                assert peer.commit(plan,mode="START").outcome=="CONFIRMED"
        with original(store) as connection:yield connection
    s.relocation.begin(owner_authorized=True)
    save=s.relocation.context.store._save_locked
    def armed(*args,**kwargs):
        result=save(*args,**kwargs)
        if result.payload["dispatch"]=="INVOKING":raced.armed=True
        return result
    monkeypatch.setattr(s.relocation.context.store,"_save_locked",armed)
    monkeypatch.setattr(FolderStore,"connection",raced)
    monkeypatch.setattr(s.native,"run",lambda *a:calls.append(a))
    proof=s.relocation._proof
    def verified(state,document=None,**kwargs):
        try:return proof(state,document,**kwargs)
        except ConfigurationError as error:
            if document is not None:
                refusals.append((str(error),state["dispatch"],
                    document["records"]["global.force_request"]["body"]["request_id"],kwargs.get("sql_revision")))
            raise
    monkeypatch.setattr(s.relocation,"_proof",verified)
    # The native port exposes an opaque error for exceptions from its body.
    # Require the actual underlying held-SQL owner proof, not that outer code.
    with pytest.raises(SettingsError,match="SETTINGS_STORE_UNAVAILABLE"):
        s.relocation.advance(owner_authorized=True)
    assert len(refusals)==1 and refusals[0][:3]==("OWNER_SUPERSEDED","INVOKING",tid("last-folder-force"))
    assert type(refusals[0][3]) is int and refusals[0][3]>=1
    assert entered[0] and not calls and v.port.root.exists() and not v.target.exists()
    assert s.relocation._state()[0]["dispatch"]=="INVOKING"
    assert s.ctx.effects.receipt(Action.IDENTITY)["outcome"]=="UNKNOWN"


def test_actual_candidate_environment_failure_prevents_native_intent_and_shared_plan(value,monkeypatch):
    s=value;before=s.ctx.leadership.backend.read().raw
    monkeypatch.setattr(s.checker,"environment",lambda:None)
    with pytest.raises(ConfigurationError,match="REVALIDATION_REQUIRED"):
        s.relocation.begin(owner_authorized=True)
    assert s.relocation.context.store.read() is None and s.ctx.leadership.backend.read().raw==before


@pytest.mark.parametrize("fault",["other-unknown","duplicate-digest","sender-owner","sender-epoch","native-election"])
def test_own_unknown_never_allows_other_work_changed_sender_or_pending_native_election(value,monkeypatch,fault):
    s=value;v=s.value;s.relocation.begin(owner_authorized=True)
    start=s.ctx.effects.start;calls=[];captured=[];profile=v.setup.store.read()
    def inject(*args,**kwargs):
        assert start(*args,**kwargs)=="CONFIRMED"
        cp=s.ctx.checkpoint.read();backend=s.ctx.leadership.backend
        if fault=="native-election":
            leader=s.ctx.leadership
            plan=leader.renew(leader.observe(s.ctx.clock()),cp.grant,transition=tid("folder-pending-renew"))
            assert s.ctx.checkpoint.replace(cp,replace(cp,election=plan))
        else:
            snap=backend.read();doc=snap.document();value=ledger(doc["records"][SLOT])
            own=value["entries"][Action.IDENTITY.value]
            if fault in {"other-unknown","duplicate-digest"}:
                value["entries"][Action.SSH.value]={**own,"operation_id":
                    own["operation_id"] if fault=="duplicate-digest" else "b"*64}
            elif fault=="sender-owner":own["owner"]=ACTORS[1]
            else:own["epoch"]+=1
            doc["records"][SLOT]=changed_row(doc["records"][SLOT],value)
            assert backend.compare_replace(snap,doc)==WriteResult.ACCEPTED
        captured.append(backend.read().raw)
        return "CONFIRMED"
    monkeypatch.setattr(s.ctx.effects,"start",inject)
    monkeypatch.setattr(s.native,"run",lambda *a:calls.append(a))
    with pytest.raises(ConfigurationError):s.relocation.advance(owner_authorized=True)
    assert len(captured)==1 and s.ctx.leadership.backend.read().raw==captured[0]
    assert not calls and v.port.root.exists() and not v.target.exists()
    assert v.setup.store.read()==profile and s.relocation._state()[0]["dispatch"]=="PREPARED"
    assert s.ctx.effects.receipt(Action.IDENTITY)["outcome"]=="UNKNOWN"
    with pytest.raises(ConfigurationError):s.relocation.inspect()


def test_shared_folder_plan_cannot_be_mutated_or_erased_by_an_effect_transition(value):
    s=value;s.relocation.begin(owner_authorized=True)
    state,_=s.relocation._state();assert s.relocation._plan(state)=="CONFIRMED"
    snap=s.ctx.leadership.backend.read();doc=snap.document();before=ledger(doc["records"][SLOT])
    cp=s.ctx.checkpoint.read()
    for fault in ("erase","replace","ordinary"):
        bad=copy.deepcopy(before)
        if fault=="erase":bad.pop("folder_plan")
        elif fault=="replace":bad["folder_plan"]["mapping_sha256"]="b"*64
        else:bad["entries"]["IDENTITY"]=dict(owner=cp.grant.owner,epoch=cp.grant.epoch,operation_id="c"*64,outcome="UNKNOWN")
        with pytest.raises(ConfigurationError):
            EffectMutation.prepare(snap,OwnerGuard(cp.grant.owner,cp.grant.epoch),
                changed_row(doc["records"][SLOT],bad),purpose="START")
    assert s.ctx.leadership.backend.read().raw==snap.raw


def test_native_operation_store_alias_is_refused_before_any_intent(value):
    s=value
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
        FolderRelocation(replace(s.relocation.context,store=s.candidate.context.profile))
