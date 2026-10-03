"""Actual Linux folder/C1/native mapping and unchanged ordinary helper transport."""
import copy
from dataclasses import asdict,replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tb4.commissioning_checks import CommissionedStorage
from tb4.configuration_contract import ConfigurationError
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import DB,JOURNAL,FolderConfig,FolderStore,identity
from tb4.drive.folder_helper import load_config
from tb4.drive.folder_mapping import (FolderPathMapping,FolderMappingContext,FolderMappingPreparation,
                                     FolderMappedCommissioning,SCHEMA)
from tb4.drive.folder_protocol import header
from tb4.private_settings import SettingsError
from tb4.exchange_layout import encoded
from tests.drive.test_folder_commissioning import context  # noqa: F401 - real isolated ext4/xfs fixture
from tests.drive.folder_mapping_support import system

pytestmark=pytest.mark.skipif(sys.platform!="linux",reason="native Linux server-local folder mapping")


@pytest.fixture
def value(context,tmp_path):
    return system(context,tmp_path)


def private_config(value,tmp_path):
    config=value.port._config()
    result=dict(version=1,root=config.binding.root_id,domain=config.binding.domain_id,path=str(config.root),
        root_dev=config.root_identity[0],root_ino=config.root_identity[1],
        db_dev=config.db_identity[0],db_ino=config.db_identity[1],
        journal_dev=config.journal_identity[0],journal_ino=config.journal_identity[1])
    path=tmp_path/"server-config.json";path.write_bytes(encoded(result));path.chmod(0o600)
    return path,config


def inventory(value):
    return {p.name:(identity(p),os.getxattr(p,"user.tb4.commissioning") if p.name!=JOURNAL else None,
                    p.read_bytes() if p.name not in {DB,JOURNAL} else None) for p in value.port.root.iterdir()}


def test_actual_c1_prepares_one_immutable_native_lookup_and_no_role_or_work_or_profile_mutation(value):
    v=value;before=v.leader.backend.read().raw;profile=v.setup.store.read();files=inventory(v)
    assert v.creator.prepare(owner_authorized=True)=="LOOKUP_PREPARED"
    state=v.mapping.read()
    assert state["authority"]==asdict(v.port.binding) and state["base_setup_sha256"]
    from jsonschema import Draft202012Validator
    Draft202012Validator(json.loads((Path(__file__).parents[2]/SCHEMA).read_bytes())).validate(state)
    assert v.mapping.store.read().revision==1 and v.mapping.store.read().previous is None
    assert v.mapping.select(v.port._config())==v.port._config()
    assert v.leader.backend.read().raw==before and v.setup.store.read()==profile
    assert inventory(v)==files and not v.target.exists()
    with pytest.raises(ConfigurationError,match="EXISTS"):
        v.creator.prepare(owner_authorized=True)
    assert v.mapping.store.read().revision==1


def test_existing_static_and_exact_mapped_helper_keep_same_authority_after_owned_fixture_rename(value,tmp_path):
    v=value;path,config=private_config(v,tmp_path);files=inventory(v);before=v.leader.backend.read().raw
    assert load_config(path)==config
    assert load_config(path,mapping_store=v.mapping.store.native.root)==config
    v.creator.prepare(owner_authorized=True)
    mapped=FolderMappedCommissioning(v.port,config,v.mapping)
    assert CommissionedStorage(mapped).verify(v.setup.private_choices()["storage"])
    # This test-only rename tests read lookup; no product rename API exists.
    v.port.root.rename(v.target)
    assert load_config(path,mapping_store=v.mapping.store.native.root).root==v.target
    assert v.mapping.select(config).root==v.target
    assert mapped.inspect_authority(v.spec,v.handle)==v.handle
    assert mapped.authority(v.handle).read().raw==before
    assert CommissionedStorage(mapped).verify(v.setup.private_choices()["storage"])
    assert {p.name:(identity(p),os.getxattr(p,"user.tb4.commissioning") if p.name!=JOURNAL else None,
                   p.read_bytes() if p.name not in {DB,JOURNAL} else None) for p in v.target.iterdir()}==files
    with pytest.raises(AuthorityError):
        FolderStore(load_config(path)).read()
    request={**header(v.port.binding,"a"*32),"operation":"READ"}
    result=subprocess.run([sys.executable,"-m","tb4.drive.folder_helper","--config",str(path),
        "--mapping-store",str(v.mapping.store.native.root)],input=encoded(request),capture_output=True,timeout=10)
    assert result.returncode==0
    reply=json.loads(result.stdout)
    assert reply["result"]=="SNAPSHOT" and reply["root"]==v.spec.root_id
    assert set(reply)==set(request)-{"operation"}|{"result","revision","body"}
    assert v.setup.private_choices()["storage"]["authority"]==v.handle.record()


@pytest.mark.parametrize("fault",["owner","profile","source","work","force","clock","caps","target",
                                 "parent","store-alias","mapping-in-root"])
def test_actual_preparation_refuses_unqualified_inputs_before_any_mapping_or_root_change(value,tmp_path,fault):
    v=value;owner=True;creator=v.creator
    if fault=="owner":owner=False
    elif fault=="profile":
        revision=v.setup.snapshot.revision
        v.setup.choose({"network_scope":v.setup.private_choices()["network_scope"]})
        assert v.setup.snapshot.revision==revision+1
    elif fault=="source":v.source.fail_resolve=True
    elif fault=="work":
        backend=v.leader.backend
        snapshot=backend.read();document=snapshot.document()
        document["records"]["target.000.work"].update(generation=1,operation_id="b"*64,retention="UNREAD")
        assert backend.compare_replace(snapshot,document).value=="ACCEPTED"
    elif fault=="force":
        from tb4.drive.leadership import Leadership
        from tests.drive.test_native_leadership import ACTORS,ENROLLMENT,tid
        peer=Leadership(v.leader.backend,actor=ACTORS[1],enrollment=ENROLLMENT)
        plan=peer.request_force(peer.observe(v.ctx.clock()),request_id=tid("mapping-force"),user_requested=True)
        assert peer.commit(plan,mode="START").outcome=="CONFIRMED"
    elif fault=="clock":object.__setattr__(v.ctx,"clock",lambda:None)
    elif fault=="caps":object.__setattr__(v.ctx,"capabilities",lambda:None)
    elif fault=="target":v.target.mkdir(mode=0o700)
    elif fault=="parent":
        broad=tmp_path/"public-parent";broad.mkdir(mode=0o755)
        object.__setattr__(creator.context,"target",broad/"destination")
    elif fault in {"store-alias","mapping-in-root"}:
        from tb4.private_settings import native_settings
        store=v.stores[0] if fault=="store-alias" else native_settings(
            v.port.root/"unsafe-mapping",create=True,owner_authorized=True)
        with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
            FolderMappingPreparation(replace(creator.context,mapping=FolderPathMapping(store)))
        assert v.mapping.read() is None
        return
    before=v.leader.backend.read().raw;profile=v.setup.store.read();files=inventory(v)
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        creator.prepare(owner_authorized=owner)
    assert v.mapping.read() is None and v.leader.backend.read().raw==before
    assert v.setup.store.read()==profile and inventory(v)==files


@pytest.mark.parametrize("fault",["foreign-target","missing","symlink","database","journal","parent","frame"])
def test_exact_lookup_refuses_missing_aliases_replacement_or_mutated_frame(value,tmp_path,fault):
    v=value;config=v.port._config();v.creator.prepare(owner_authorized=True)
    if fault=="foreign-target":v.target.mkdir(mode=0o700)
    elif fault=="missing":v.port.root.rename(tmp_path/"unplanned-location")
    elif fault=="symlink":v.target.symlink_to(v.port.root,target_is_directory=True)
    elif fault in {"database","journal"}:
        old=v.port.root/(DB if fault=="database" else JOURNAL)
        old.rename(v.port.root/"retained-replaced-object")
        old.write_bytes(b"synthetic replacement");old.chmod(0o600)
    elif fault=="parent":v.port.root.parent.chmod(0o755)
    else:
        snapshot=v.mapping.store.read();bad=copy.deepcopy(snapshot.payload);bad["extra"]="invalid"
        v.mapping.store.save(bad,expected_revision=snapshot.revision)
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        v.mapping.select(config)


def test_unconfirmed_first_native_mapping_is_denied_and_exact_c1_recovery_sends_no_filesystem_move(value,monkeypatch):
    v=value;store=v.mapping.store;before=v.leader.backend.read().raw;original=store.native.locked
    from contextlib import contextmanager
    @contextmanager
    def cut():
        with original() as port:
            class Proxy:
                def __getattr__(self,name):return getattr(port,name)
                def promote(self):raise OSError("SYNTHETIC_BEFORE_MAPPING_PROMOTION")
            yield Proxy()
    monkeypatch.setattr(store.native,"locked",cut)
    with pytest.raises(SettingsError):
        v.creator.prepare(owner_authorized=True)
    monkeypatch.setattr(store.native,"locked",original)
    with pytest.raises(SettingsError,match="RECOVERY_REQUIRED"):
        v.mapping.select(v.port._config())
    assert v.creator.recover_local(owner_authorized=True)=="LOOKUP_PREPARED"
    assert v.mapping.select(v.port._config())==v.port._config() and not v.target.exists()
    assert v.leader.backend.read().raw==before
