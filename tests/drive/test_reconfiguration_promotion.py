"""Actual native-profile/first-run boundaries; no runtime activation."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import pytest

from tb4.commissioning_state import Setup,DenyActivation
from tb4.configuration_contract import ConfigurationError
from tb4.credential_contract import CredentialResolver,Outcome,Purpose
from tb4.drive.docs_authority import AuthorityError
from tb4.private_settings import SettingsError
from tb4.reconfiguration_candidate import DERIVED
from tb4.reconfiguration_promotion import ProfilePromotion,SCHEMA,SCHEMA_SHA256
from reconfiguration_promotion_support import system
from reconfiguration_rebind_support import TARGET,fallback
from tests.security.test_credential_contract import FixtureStore,TARGET as DEVICE,TRUST


def test_actual_exact_profile_promotion_retains_archive_identity_history_authority_work_and_closes_activation():
    s=system();v=s.value;original=v.setup.store.read();document=copy.deepcopy(v.provider.store.document)
    writes=len(v.provider.store.calls);archive=s.publication.post_root.context.archive.read()
    assert s.promotion.begin(s.checker,owner_authorized=True)=="PREPARED"
    assert v.setup.store.read()==original
    assert s.promotion.advance(s.checker,owner_authorized=True)=="PROFILE_PROMOTED"
    actual=v.setup.store.read()
    assert actual.revision==original.revision+1 and actual.previous==original.payload
    assert actual.payload["choices"]["storage"]["spec"]["root_id"]==TARGET
    assert all(actual.payload[k]==original.payload[k] for k in ("installation_id","setup_nonce","operations"))
    assert actual.payload["credential_image"]==original.payload["credential_image"]
    assert actual.payload.get("network_table")==original.payload.get("network_table")
    assert set(actual.payload)&DERIVED=={"ballpark_publication"}
    assert actual.payload["ballpark_publication"]["pending"] is None
    assert actual.payload["state"]=="INCOMPLETE" and actual.payload["reason"]=="REVALIDATION_REQUIRED"
    assert s.publication.post_root.context.archive.read()==archive and archive.payload["profile"]==original.payload
    assert ProfilePromotion(s.context).advance(s.checker,owner_authorized=True)=="PROFILE_PROMOTED"
    assert v.setup.store.read()==actual and v.provider.store.document==document and len(v.provider.store.calls)==writes
    assert v.checkpoint.read().maintenance is not None
    assert not Setup(v.setup.store).status()["settings_validated"] and not s.promotion.view()["runtime_active"]
    assert not s.promotion.view()["automatic_replay"]


@pytest.mark.parametrize("fault",["source","permission","stage","original","work","archive","commit","environment"])
def test_actual_changed_facts_refuse_native_promotion_without_original_or_remote_write(fault):
    s=system();v=s.value;s.promotion.begin(s.checker,owner_authorized=True)
    original=v.setup.store.read();writes=len(v.provider.store.calls)
    if fault=="source":v.source.catalog["profiles"][0]["status"]="REVOKED";v.source.save()
    elif fault=="permission":v.provider.metadata[TARGET]["capabilities"]["canEdit"]=False
    elif fault=="stage":Setup(s.publication.post_root.context.profile).choose({"network_scope":["192.0.2.0/24"]})
    elif fault=="original":v.setup.choose({"network_scope":v.setup.private_choices()["network_scope"]})
    elif fault=="work":v.provider.store.document["records"]["target.000.status"]["body"]={"synthetic":True}
    elif fault=="archive":
        store=s.publication.post_root.context.archive;current=store.read();store.save(current.payload,expected_revision=current.revision)
    elif fault=="commit":
        store=s.publication.context.store;current=store.read();store.save({**current.payload,"dispatch":"INVOKING"},expected_revision=current.revision)
    else:s.checker.environment=lambda:None
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        s.promotion.advance(s.checker,owner_authorized=True)
    if fault!="original":assert v.setup.store.read()==original
    assert len(v.provider.store.calls)==writes


def test_actual_lost_credentials_after_published_first_run_refuse_promotion_without_execution():
    stores=[]
    def credentials(s):
        store=FixtureStore(s.value.setup.installation_id);resolver=CredentialResolver(store.installation_id,store,clock=lambda:store.now)
        handle=resolver.enroll(target_id=DEVICE,target_trust=TRUST,store_locator="synthetic-promotion-slot",
            purposes=frozenset({Purpose.FETCHER_STATUS}),expires_at=200,owner_authorized=True)
        s.post_root.candidate.choose({"credentials":[dict(handle=handle,target_id=DEVICE,target_trust=TRUST,
            purposes=[Purpose.FETCHER_STATUS.value])]},owner_authorized=True)
        s.checker.credentials=resolver;stores.append(store)
    s=system(prepare=credentials);v=s.value;s.promotion.begin(s.checker,owner_authorized=True)
    original=v.setup.store.read();writes=len(v.provider.store.calls);stores[0].state=Outcome.REVOKED
    with pytest.raises(SettingsError,match="CREDENTIAL_UNAVAILABLE"):
        s.promotion.advance(s.checker,owner_authorized=True)
    assert stores[0].executions==0 and v.setup.store.read()==original and len(v.provider.store.calls)==writes


def test_actual_topology_launcher_candidate_is_promoted_from_its_qualified_first_run():
    def choices(s):
        descriptor=copy.deepcopy(s.post_root.context.profile.read().payload["choices"]["descriptor"])
        descriptor["topology"]="ROUTED"
        first=descriptor["devices"][0]
        first["launch_mode"]={r:"EXTERNAL" for r in first["roles"]}
        s.post_root.candidate.choose({"network_scope":["198.51.100.0/24"],"descriptor":descriptor},owner_authorized=True)
    s=system(prepare=choices);original=s.value.setup.store.read();s.promotion.begin(s.checker,owner_authorized=True)
    assert s.promotion.advance(s.checker,owner_authorized=True)=="PROFILE_PROMOTED"
    choices=s.value.setup.store.read().payload["choices"]
    assert choices["network_scope"]==["198.51.100.0/24"] and choices["descriptor"]["topology"]=="ROUTED"
    assert set(choices["descriptor"]["devices"][0]["launch_mode"].values())=={"EXTERNAL"}
    assert s.value.setup.store.read().payload["operations"]==original.payload["operations"]


def test_actual_candidate_change_during_first_run_probe_cannot_replace_original():
    s=system();v=s.value;s.promotion.begin(s.checker,owner_authorized=True)
    original=v.setup.store.read();writes=len(v.provider.store.calls);environment=s.checker.environment;changed=[]
    def late():
        if not changed:
            changed.append(True);Setup(s.publication.post_root.context.profile).choose({"network_scope":[]})
        return environment()
    s.checker.environment=late
    with pytest.raises((ConfigurationError,SettingsError,AuthorityError)):
        s.promotion.advance(s.checker,owner_authorized=True)
    assert changed and v.setup.store.read()==original and len(v.provider.store.calls)==writes


def test_actual_first_cas_fallback_does_not_require_origin_profile_promotion_acknowledgement():
    s=system();v=s.value;s.promotion.begin(s.checker,owner_authorized=True)
    current=fallback(s.publication.post_root.rebind)
    writes=len(v.provider.store.calls)
    assert v.provider.store.document["records"]["global.leadership"]["body"]["epoch"]==2
    assert s.promotion.advance(s.checker,owner_authorized=True)=="PROFILE_PROMOTED"
    assert len(v.provider.store.calls)==writes and current.ctx.setup.store.read().payload["installation_id"]!=v.setup.installation_id
    assert v.checkpoint.read().maintenance is not None and not s.promotion.view()["runtime_active"]


def test_closed_named_promotion_schema_store_alias_and_native_frame_budget():
    from jsonschema import Draft202012Validator
    s=system();raw=(Path(__file__).parents[2]/SCHEMA).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SCHEMA_SHA256
    with pytest.raises(ConfigurationError,match="STORE_ALIAS"):
        ProfilePromotion(replace(s.context,store=s.value.setup.store))
    s.promotion.begin(s.checker,owner_authorized=True);state=s.context.store.read().payload
    schema=json.loads(raw);check=Draft202012Validator(schema["$defs"]["profilePromotion"])
    assert check.is_valid(state) and not check.is_valid({**state,"extra":True})
    assert not Draft202012Validator(schema).is_valid(state) and len(state["pin"]["files"])<=17
    original=s.value.setup.store.read();writes=len(s.value.provider.store.calls)
    # Native frame budget only, not a valid setup or an admission attempt.
    with pytest.raises(ConfigurationError,match="PROMOTION_NATIVE_SIZE"):
        s.promotion._budget({"synthetic":"s"*(600*1024)},{"synthetic":"s"*(600*1024)},original.revision)
    assert s.value.setup.store.read()==original and len(s.value.provider.store.calls)==writes
