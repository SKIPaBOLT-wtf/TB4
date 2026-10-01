import copy
import json
from dataclasses import replace

import pytest

from tb4.discovery_catalogue import (Catalogue, DiscoveryError, Interface, Observation,
    Scope, TrustView, VerifiedBinding, freshness, new_image, validate_image)

INSTALLATION = "11111111-1111-4111-8111-111111111111"
DOMAIN = "22222222-2222-4222-8222-222222222222"
KNOWN = "33333333-3333-4333-8333-333333333333"
OTHER = "44444444-4444-4444-8444-444444444444"
POLICY = Scope((Interface("synthetic-lan", 7, ("192.0.2.0/24",), "LAN"),
                Interface("synthetic-vpn", 9, ("2001:db8::/64", "198.51.100.0/24"), "VPN")),
               frozenset({"NEIGHBOR_CACHE", "ICMP", "FIXED_HELPER"}))


def observed(**changes):
    base = dict(interface_index=7, address="192.0.2.8", source="NEIGHBOR_CACHE",
                observed_at=100, valid_for_s=60, hardware_hint="synthetic-hint-a",
                name_hint="SYNTHETIC_PRIVATE_CANARY")
    return Observation(**(base | changes))


def catalogue(capacity=4, quarantine=2):
    return Catalogue(new_image(INSTALLATION, DOMAIN, capacity=capacity,
                               quarantine_capacity=quarantine))


@pytest.mark.parametrize("changes", [
    {"interface_index":8}, {"address":"203.0.113.5"},
    {"interface_index":7,"address":"2001:db8::8"},
    {"interface_index":9,"address":"192.0.2.8"},
])
def test_scope_requires_both_exact_interface_and_authorized_subnet(changes):
    model=catalogue(); before=model.private_image()
    assert model.observe((observed(**changes),),POLICY,now=100)==("OUT_OF_SCOPE",)
    assert model.private_image()==before


def test_empty_isolated_scope_and_unapproved_method_do_not_observe():
    model=catalogue()
    assert model.observe((observed(),),Scope(()),now=100)==("OUT_OF_SCOPE",)
    assert model.observe((observed(source="ICMP",online=True),),
                         replace(POLICY,methods=frozenset({"NEIGHBOR_CACHE"})),now=100)==("OUT_OF_SCOPE",)
    assert model.status()["used"]==0


def test_routed_ipv6_and_icmp_unavailable_do_not_imply_offline_or_fetcher():
    model=catalogue()
    item=observed(interface_index=9,address="2001:db8::8",source="FIXED_HELPER",online=True)
    assert model.observe((item,),POLICY,now=100)==("OBSERVED",)
    row=model.shared(now=100)[0]
    assert row["network"]["value"]=="ONLINE" and row["trust"]=="UNTRUSTED"
    assert not ({"ssh_auth","fetcher_liveness","acceptance","result","installation"} & set(row))
    assert model.shared(now=160)[0]["network"]["value"]=="UNKNOWN"


def test_cache_is_not_current_reachability_proof():
    with pytest.raises(DiscoveryError):
        observed(online=True)
    model=catalogue();model.observe((observed(),),POLICY,now=100)
    assert model.shared(now=100)[0]["network"]["value"]=="UNKNOWN"
    assert model.shared(now=100)[0]["network"]["source"]=="NONE"


@pytest.mark.parametrize("now,trusted,outcome", [(160,True,"STALE"),(99,True,"CLOCK_UNCERTAIN"),
                                                (100,False,"CLOCK_UNCERTAIN")])
def test_old_or_uncertain_time_cannot_refresh_catalogue(now,trusted,outcome):
    model=catalogue();before=model.private_image()
    assert model.observe((observed(),),POLICY,now=now,clock_trusted=trusted)==(outcome,)
    assert model.private_image()==before


def test_identity_alias_persist_while_hostname_is_only_a_hint():
    model=catalogue();model.observe((observed(),),POLICY,now=100)
    original=model.private_image(); row=model.shared(now=100)[0]
    restarted=Catalogue(json.loads(json.dumps(original)))
    restarted.observe((observed(name_hint="renamed-synthetic",observed_at=101),),POLICY,now=101)
    assert restarted.shared(now=101)[0]["device_id"]==row["device_id"]
    assert restarted.shared(now=101)[0]["alias"]==row["alias"]
    assert row["device_id"] not in {INSTALLATION,DOMAIN}
    assert original["entries"][0]["endpoints"][0]["name_hint"]=="SYNTHETIC_PRIVATE_CANARY"


def test_duplicate_hostnames_are_distinct_untrusted_catalogue_entries():
    model=catalogue()
    model.observe((observed(),observed(address="192.0.2.9",hardware_hint="synthetic-hint-b")),
                  POLICY,now=100)
    rows=model.shared(now=100)
    assert len({r["device_id"] for r in rows})==2
    assert len({r["alias"] for r in rows})==2
    assert all(r["trust"]=="UNTRUSTED" for r in rows)


@pytest.mark.parametrize("hint", ["synthetic-reassigned", None])
def test_address_reassignment_or_lost_hardware_hint_is_quarantined(hint):
    model=catalogue();model.observe((observed(),),POLICY,now=100)
    before=model.private_image()["entries"]
    assert model.observe((observed(hardware_hint=hint,observed_at=101),),POLICY,now=101)==("ADDRESS_IDENTITY_CHANGED",)
    assert model.private_image()["entries"]==before and model.status()["quarantined"]==1


def test_same_hardware_hint_on_another_interface_never_merges_identity():
    model=catalogue();model.observe((observed(),),POLICY,now=100)
    assert model.observe((observed(interface_index=9,address="198.51.100.7"),),POLICY,now=100)==("HINT_COLLISION",)
    assert model.status()["used"]==1


def test_verified_peer_tracks_multiple_mutable_addresses_with_one_alias():
    model=catalogue();model.seed(0,KNOWN,"approved-device")
    items=(observed(source="FIXED_HELPER",online=True),
           observed(interface_index=9,address="2001:db8::8",source="FIXED_HELPER",
                    online=True,hardware_hint="changed-native-hint"))
    trust=TrustView(frozenset({KNOWN}),tuple(VerifiedBinding(KNOWN,o.interface_index,o.address,o.observed_at) for o in items))
    assert model.observe(items,POLICY,now=100,trust=trust)==("OBSERVED","OBSERVED")
    assert model.status()["used"]==1 and len(model.private_image()["entries"][0]["endpoints"])==2
    assert model.shared(now=100,trust=trust)[0]["trust"]=="ENROLLED"
    # Revoked/missing enrollment is reflected immediately, never stored as a READY flag.
    assert model.shared(now=100)[0]["trust"]=="UNTRUSTED"


def test_unverified_observation_cannot_refresh_trusted_target_or_copy_its_trust():
    model=catalogue();model.seed(0,KNOWN,"approved")
    item=observed(source="FIXED_HELPER",online=True)
    trust=TrustView(frozenset({KNOWN}),(VerifiedBinding(KNOWN,7,item.address,100),))
    model.observe((item,),POLICY,now=100,trust=trust)
    before=model.private_image()["entries"]
    assert model.observe((observed(observed_at=101),),POLICY,now=101,trust=trust)==("IDENTITY_UNCONFIRMED",)
    assert model.private_image()["entries"]==before
    # A stale proof and an ICMP result cannot authenticate a peer.
    assert trust.proven(replace(item,observed_at=101)) is None
    assert trust.proven(replace(item,source="ICMP")) is None


def test_conflicting_verified_address_never_reassigns_existing_target():
    model=catalogue();model.seed(0,KNOWN,"approved");model.seed(1,OTHER,"other")
    first=observed(source="FIXED_HELPER",online=True)
    model.observe((first,),POLICY,now=100,trust=TrustView(frozenset({KNOWN}),
                    (VerifiedBinding(KNOWN,7,first.address,100),)))
    before=model.private_image()["entries"]
    next_item=replace(first,observed_at=101)
    trust=TrustView(frozenset({KNOWN,OTHER}),(VerifiedBinding(OTHER,7,first.address,101),))
    assert model.observe((next_item,),POLICY,now=101,trust=trust)==("VERIFIED_IDENTITY_CONFLICT",)
    assert model.private_image()["entries"]==before


def test_full_catalogue_and_quarantine_preserve_all_existing_records():
    model=catalogue(capacity=1,quarantine=1)
    model.observe((observed(),),POLICY,now=100)
    before=model.private_image()["entries"]
    for address_ in ("192.0.2.9","192.0.2.10"):
        assert model.observe((observed(address=address_,hardware_hint=address_),),POLICY,now=100)==("CAPACITY_FULL",)
    assert model.private_image()["entries"]==before
    assert model.status()==dict(used=1,capacity=1,quarantined=1,quarantine_capacity=1,
                               overflow=True,automatic_enrollment=False)


def test_same_ambiguous_endpoint_updates_one_quarantine_slot():
    model=catalogue();model.observe((observed(),),POLICY,now=100)
    for timestamp in range(101,110):
        model.observe((observed(observed_at=timestamp,hardware_hint="changed"),),POLICY,now=timestamp)
    assert model.status()["quarantined"]==1 and not model.status()["overflow"]


def test_batch_rejection_is_atomic_and_cannot_expand_freshness():
    model=catalogue();before=model.private_image()
    with pytest.raises(DiscoveryError,match="FRESHNESS_POLICY"):
        model.observe((observed(),observed(address="192.0.2.9",valid_for_s=61)),POLICY,now=100)
    assert model.private_image()==before
    with pytest.raises(DiscoveryError,match="BATCH"):
        model.observe((observed(),)*257,POLICY,now=100)


def test_older_observation_does_not_replace_newer_evidence():
    model=catalogue();model.observe((observed(observed_at=101),),POLICY,now=101)
    before=model.private_image()
    assert model.observe((observed(),),POLICY,now=101)==("OLDER_OBSERVATION",)
    assert model.private_image()==before


def test_public_projection_and_repr_exclude_protected_observations(capsys):
    model=catalogue();item=observed();model.observe((item,),POLICY,now=100)
    public=json.dumps(model.shared(now=100))+json.dumps(model.status())+repr(item)+repr(POLICY)
    for value in ("192.0.2.8","synthetic-hint-a","SYNTHETIC_PRIVATE_CANARY","synthetic-lan",INSTALLATION):
        assert value not in public
    assert capsys.readouterr()==("","")


@pytest.mark.parametrize("change", [
    lambda i:i.update(extra="SYNTHETIC_PRIVATE_CANARY"),
    lambda i:i.update(installation_id="bad"),
    lambda i:i.update(revision=True),
    lambda i:i.update(quarantine=[]),
    lambda i:i["entries"].append(i["entries"][0]),
    lambda i:i["entries"][0]["endpoints"][0].update(online=True),
])
def test_malformed_or_duplicated_private_image_is_rejected(change):
    model=catalogue();model.observe((observed(),),POLICY,now=100)
    image=model.private_image();change(image)
    with pytest.raises(DiscoveryError) as exc:
        validate_image(image)
    assert "CANARY" not in str(exc.value)


def test_foreign_installation_or_domain_cannot_restore_private_image():
    image=catalogue().private_image()
    with pytest.raises(DiscoveryError):
        validate_image(image,installation_id=OTHER)
    with pytest.raises(DiscoveryError):
        validate_image(image,domain_id=OTHER)
