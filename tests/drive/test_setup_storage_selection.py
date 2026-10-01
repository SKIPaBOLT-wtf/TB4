"""Owner-selected root resolves to exact prior RP019 identities without mutation."""
import copy
import sys

import pytest

from tb4.desktop.setup_storage import ConnectedDocsSelection, BoundFolderSelection
from tb4.private_settings import SettingsError
from test_first_run_storage import prepared
from test_folder_commissioning import context, initialized, finish


def test_first_root_selection_derives_domain_and_then_uses_exact_ids():
    spec,provider,port,record=prepared()
    selector=ConnectedDocsSelection(provider,provider,llm_authorized=True)
    choices=dict(storage=None,storage_request=dict(mode="NATIVE_DOCS",location=spec.root_id))
    before=copy.deepcopy(provider.created)
    selected=selector(choices)
    assert selected.record==record
    assert provider.created==before
    provider.calls.clear()
    selector({**choices,"storage":selected.record}).verifier.verify(selected.record)
    assert all(name=="files.get" for name,_ in provider.calls)
    assert provider.created==before


@pytest.mark.skipif(sys.platform!="linux",reason="actual qualified Linux folder")
def test_actual_folder_selection_checks_same_mount_and_existing_domain(context):
    spec,port,_=context
    _,handle,commissioner=initialized(context)
    finish(commissioner)
    choices=dict(storage=None,storage_request=dict(mode=port.mode,location=str(port.root)))
    selected=BoundFolderSelection(port)(choices)
    assert selected.record["authority"]==handle.record()
    assert selected.record["spec"]["domain_id"]==spec.domain_id
    selected.verifier.verify(selected.record)
    with pytest.raises(SettingsError,match="STORAGE_UNAVAILABLE"):
        BoundFolderSelection(port)({**choices,"storage_request":dict(mode=port.mode,location="/unselected")})


@pytest.mark.parametrize("failure",["no-authorization","missing-authority","ambiguous","unready","wrong-root"])
def test_root_selection_never_creates_or_adopts_ambiguous_identity(failure):
    spec,provider,_,record=prepared()
    choices=dict(storage=None,storage_request=dict(mode="NATIVE_DOCS",location=spec.root_id))
    before=copy.deepcopy(provider.created)
    if failure=="missing-authority":
        del provider.metadata[record["authority"]["object_id"]]
    elif failure=="ambiguous":
        provider.metadata["another-authority"]=copy.deepcopy(provider.metadata[record["authority"]["object_id"]])
        provider.metadata["another-authority"]["id"]="another-authority"
    elif failure=="unready":
        provider.store.document["records"]["global.commissioning"]["body"]["state"]="PREPARING"
    elif failure=="wrong-root":
        choices["storage_request"]["location"]="different-root"
    with pytest.raises(SettingsError,match="STORAGE_UNAVAILABLE"):
        ConnectedDocsSelection(provider,provider,llm_authorized=failure!="no-authorization")(choices)
    assert provider.created==before
