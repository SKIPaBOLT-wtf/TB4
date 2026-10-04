"""Required actual Linux retained-root publication and native mapped selection."""
import copy
from dataclasses import replace
import os
from pathlib import Path
import sys

import pytest

from tb4.commissioning_checks import CommissionedStorage
from tb4.configuration_contract import ConfigurationError,configuration
from tb4.desktop.setup_storage import BoundFolderSelection
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_authority import DB,identity
from tb4.private_settings import SettingsError
from tb4.reconfiguration_admission import AdmissionContext,ConfigurationAdmission
from tb4.reconfiguration_effects import SLOT,ledger,changed_row
from tb4.reconfiguration_retained import RetainedConfigurationCommit,work_sha
from tests.drive.test_folder_commissioning import context  # noqa: F401
from tests.drive.folder_retained_support import system

pytestmark=pytest.mark.skipif(sys.platform!="linux",reason="actual same-inode Linux Folder C4 and native mapping")


@pytest.mark.parametrize("moved",[False,True])
def test_actual_same_folder_final_publication_preserves_all_fixed_artifacts_inodes_gc_and_original_profile(context,tmp_path,moved):
    s=system(context,tmp_path,moved=moved);v=s.value;port=s.ctx.storage_port
    root=port.root;storage=copy.deepcopy(v.setup.private_choices()["storage"]);before=s.ctx.leadership.backend.read().document()
    files={p.name:(identity(p),p.read_bytes() if p.name not in {DB,DB+"-journal"} else None) for p in root.iterdir()}
    marker=copy.deepcopy(before["records"]["global.commissioning"]);original=v.setup.store.read()
    assert s.commit.begin(s.checker,owner_authorized=True,decided_at=220)=="PREPARED"
    assert s.commit.advance(s.checker,owner_authorized=True)=="PUBLISHED"
    after=s.ctx.leadership.backend.read().document()
    assert configuration(after)=={**configuration(before),"revision":configuration(before)["revision"]+1,"phase":"ACTIVE"}
    assert marker==after["records"]["global.commissioning"] and work_sha(after)==work_sha(before)
    summary=ledger(before["records"][SLOT])
    assert ledger(after["records"][SLOT])=={k:x for k,x in summary.items() if k!="folder_plan"}
    assert after["records"][SLOT]==before["records"][SLOT] or moved
    assert files=={p.name:(identity(p),p.read_bytes() if p.name not in {DB,DB+"-journal"} else None) for p in root.iterdir()}
    assert v.setup.store.read()==original and v.setup.private_choices()["storage"]==storage
    assert CommissionedStorage(port).verify(storage)
    assert RetainedConfigurationCommit(s.context).advance(s.checker,owner_authorized=True)=="PUBLISHED"
    assert s.promotion.begin(s.checker,owner_authorized=True)=="PREPARED"
    assert s.promotion.advance(s.checker,owner_authorized=True)=="PROFILE_PROMOTED"
    assert v.setup.store.read().previous==original.payload and v.setup.store.read().payload["choices"]["storage"]==storage
    admission=ConfigurationAdmission(AdmissionContext(v.setup.store,v.checkpoint,s.ctx.leadership,s.checker,
        s.ctx.capabilities,s.ctx.clock))
    assert admission.release(owner_authorized=True)==configuration(after)["revision"]
    assert admission.revision()==configuration(after)["revision"]
    assert port.root==root and v.setup.store.read().payload["state"]=="INCOMPLETE"


def test_actual_mapped_selector_keeps_protected_original_lookup_anchor_and_accepts_verified_current_path(context,tmp_path):
    s=system(context,tmp_path);port=s.ctx.storage_port;choices=s.ctx.setup.private_choices()
    selector=BoundFolderSelection(port)
    for path in (port.expected.root,port.root):
        selected=selector({**choices,"storage_request":dict(mode=port.mode,location=str(path))})
        assert selected.record==choices["storage"] and selected.verifier.verify(selected.record)
    foreign=Path(tmp_path)/"foreign-folder";foreign.mkdir(mode=0o700)
    with pytest.raises(SettingsError):
        selector({**choices,"storage_request":dict(mode=port.mode,location=str(foreign))})


def test_actual_second_physical_path_or_wrong_mapping_cannot_publish_from_a_terminal_receipt(context,tmp_path):
    s=system(context,tmp_path);s.commit.begin(s.checker,owner_authorized=True,decided_at=220)
    original=s.value.setup.store.read();before=s.ctx.leadership.backend.read().document()
    # Reintroducing the original path contradicts the protected unique lookup,
    # rather than supplying proof that a replacement is the same root.
    s.ctx.storage_port.expected.root.mkdir(mode=0o700)
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        s.commit.advance(s.checker,owner_authorized=True)
    assert s.value.setup.store.read()==original
    from tb4.drive.folder_authority import FolderStore
    from tb4.drive.docs_authority import validated
    selected=s.ctx.storage_port.mapping.read();target=Path(selected["target_path"])
    config=replace(s.ctx.storage_port.expected,root=target)
    _,raw=FolderStore(config).read()
    assert validated(raw,config.binding)==before


@pytest.mark.parametrize("fault",["unknown","artifact_generation"])
def test_actual_current_folder_summary_or_retained_artifact_generation_change_refuses_final_conditional_publication(context,tmp_path,fault):
    s=system(context,tmp_path);s.commit.begin(s.checker,owner_authorized=True,decided_at=220)
    original=s.value.setup.store.read();backend=s.ctx.leadership.backend;snap=backend.read();doc=snap.document()
    if fault=="unknown":
        row=doc["records"][SLOT];value=ledger(row);value["entries"]["SSH"]=dict(
            owner=s.ctx.setup.installation_id,epoch=1,operation_id="b"*64,outcome="UNKNOWN")
        doc["records"][SLOT]=changed_row(row,value)
    else:
        # The actual fixed layout has retained artifact rows, no .gc slot.
        # Keep the allocated object/seal/body/operation/retention unchanged.
        key=s.ctx.storage_port.spec.artifact_keys[0]
        doc["records"][key]["generation"]+=1
    assert backend.compare_replace(snap,doc).name=="ACCEPTED"
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        s.commit.advance(s.checker,owner_authorized=True)
    assert backend.read().document()==doc and s.value.setup.store.read()==original
