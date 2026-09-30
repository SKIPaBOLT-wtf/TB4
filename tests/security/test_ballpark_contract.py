from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tb4.ballpark import (BallparkError, SCHEMA_BUNDLE,
                         catalogue, llm_projection, publication_candidate, validate, validate_revision)
from tb4.privacy import PrivacyError, public_artifact

DOMAIN = "00000000-0000-4000-8000-000000000001"
INSTALLATION = "00000000-0000-4000-8000-000000000002"


def observed(value, source, at=100, ttl=60):
    return dict(value=value, source=source, observed_at=at, valid_for_s=ttl)


def device(number=3):
    return dict(device_id=f"00000000-0000-4000-8000-{number:012d}", alias=f"target-{number}",
                display_name="Duplicate display names are allowed", roles=["fetcher"],
                platform=dict(os="LINUX", architecture="ARM64"), launch_mode=dict(fetcher="EXTERNAL"),
                transports=["DRIVE_API"], capabilities={}, observations={},
                interfaces=[dict(name="lan", segment="segment-a", kind="LAN", addresses=[f"192.0.2.{number}/24"])])


def fixture():
    return dict(schema_version=1, kind="BALLPARK_LOCAL", visibility="PROTECTED_LOCAL",
                installation_id=INSTALLATION, domain_id=DOMAIN, revision=1, topology="FLAT", devices=[device()])


@pytest.mark.parametrize("topology", ["FLAT", "ROUTED", "MULTI_SUBNET", "VPN", "ISOLATED", "MIXED"])
def test_topology_and_platform_variations_are_explicit(topology):
    local = fixture()
    local["topology"] = topology
    local["devices"].append(device(4))
    second = local["devices"][1]
    second["platform"] = dict(os="WINDOWS", architecture="X64")
    second["roles"] = ["watchdog", "fetcher"]
    second["launch_mode"] = dict(watchdog="DESKTOP_SESSION", fetcher="OS_SERVICE")
    second["interfaces"] = [dict(name="remote", segment="segment-b", kind="ISOLATED" if topology == "ISOLATED" else "LAN",
                                  addresses=["198.51.100.4/24"])]
    if topology in {"VPN", "MIXED"}:
        second["interfaces"].append(dict(name="vpn", segment="vpn-a", kind="VPN", addresses=["2001:db8::4/64"]))
    assert validate(local) == local
    assert len(llm_projection(catalogue(local), now=100)["devices"]) == 2


def test_projection_omits_network_paths_and_local_installation():
    local = fixture()
    local["devices"][0]["display_name"] = "protected display canary"
    shared = catalogue(local)
    summary = llm_projection(shared, now=100)
    for value in (shared, summary):
        body = json.dumps(value)
        assert "192.0.2.3" not in body and "protected display canary" not in body and INSTALLATION not in body
        assert "interfaces" not in body and "display_name" not in body
        with pytest.raises(PrivacyError, match="PUBLIC_REPORT_INVALID"):
            public_artifact("diagnostic", value)
    assert summary["devices"][0]["alias"] == "target-3"
    assert all(v["value"] == "UNKNOWN" for v in summary["devices"][0]["capabilities"].values())


@pytest.mark.parametrize("location", ["root", "device", "interface", "platform", "fact"])
def test_secret_and_unknown_fields_are_rejected_without_echo(location):
    local = fixture()
    targets = {"root": local, "device": local["devices"][0], "interface": local["devices"][0]["interfaces"][0],
               "platform": local["devices"][0]["platform"]}
    local["devices"][0]["observations"]["network"] = observed("ONLINE", "NETWORK_PROBE")
    targets["fact"] = local["devices"][0]["observations"]["network"]
    targets[location]["password"] = "synthetic-private-canary"
    with pytest.raises(BallparkError, match="BALLPARK_SCHEMA_INVALID") as error:
        validate(local)
    assert "synthetic-private-canary" not in str(error.value)


def test_shared_catalogue_cannot_add_endpoints_or_resolver_handles():
    shared = catalogue(fixture())
    for name in ("host", "credential_ref", "path", "token"):
        candidate = copy.deepcopy(shared)
        candidate["devices"][0][name] = "synthetic-private-canary"
        with pytest.raises(BallparkError, match="BALLPARK_SCHEMA_INVALID"):
            validate(candidate, shared=True)


def test_no_inference_between_network_ssh_fetcher_and_result():
    local = fixture()
    local["devices"][0]["observations"] = dict(network=observed("OFFLINE", "NETWORK_PROBE"),
        fetcher_liveness=observed("ALIVE", "RUNTIME_HEARTBEAT"), result=observed("FAILED", "CORRELATED_RESULT"))
    result = llm_projection(catalogue(local), now=110)["devices"][0]
    assert result["observations"]["network"]["value"] == "OFFLINE"
    assert result["observations"]["fetcher_liveness"]["value"] == "ALIVE"
    assert result["observations"]["result"]["value"] == "FAILED"
    assert result["observations"]["ssh_auth"]["value"] == "UNKNOWN"
    assert result["observations"]["acceptance"]["value"] == "UNKNOWN"
    assert result["capabilities"]["ssh_start"]["value"] == "UNKNOWN"


def test_each_observation_has_its_own_freshness_and_future_clock_guard():
    local = fixture()
    local["devices"][0]["observations"] = dict(network=observed("ONLINE", "NETWORK_PROBE", ttl=10),
        fetcher_liveness=observed("ALIVE", "RUNTIME_HEARTBEAT", ttl=60),
        ssh_auth=observed("AUTHORIZED", "FIXED_HELPER", at=200))
    facts = llm_projection(catalogue(local), now=110)["devices"][0]["observations"]
    assert facts["network"] == dict(value="UNKNOWN", freshness="STALE")
    assert facts["fetcher_liveness"] == dict(value="ALIVE", freshness="FRESH")
    assert facts["ssh_auth"] == dict(value="UNKNOWN", freshness="CLOCK_UNCERTAIN")


@pytest.mark.parametrize("fact", [observed("ONLINE", "OWNER_DECLARATION"), observed("ONLINE", "NONE"),
                                  observed("ONLINE", "NETWORK_PROBE", at=None), observed("ONLINE", "NETWORK_PROBE", ttl=None)])
def test_configuration_or_incomplete_observation_cannot_claim_online(fact):
    local = fixture()
    local["devices"][0]["observations"]["network"] = fact
    with pytest.raises(BallparkError, match="BALLPARK_OBSERVATION_|BALLPARK_FRESHNESS_"):
        validate(local)


def test_duplicate_display_names_allowed_but_id_alias_and_address_collisions_fail():
    local = fixture()
    local["devices"].append(device(4))
    validate(local)
    for field in ("device_id", "alias", "interfaces"):
        candidate = copy.deepcopy(local)
        candidate["devices"][1][field] = copy.deepcopy(candidate["devices"][0][field])
        with pytest.raises(BallparkError, match="COLLISION"):
            validate(candidate)


def test_same_address_on_isolated_segments_is_not_global_identity():
    local = fixture()
    local["devices"].append(device(4))
    local["devices"][1]["interfaces"][0].update(segment="segment-b", addresses=["192.0.2.3/24"])
    assert len(validate(local)["devices"]) == 2


def test_address_change_keeps_device_identity_and_requires_next_revision():
    before = fixture()
    after = copy.deepcopy(before)
    after["revision"] = 2
    after["devices"][0]["interfaces"][0]["addresses"] = ["198.51.100.3/24"]
    assert validate_revision(before, after, expected_revision=1)["devices"][0]["device_id"] == before["devices"][0]["device_id"]
    assert before["devices"][0]["interfaces"][0]["addresses"] == ["192.0.2.3/24"]
    with pytest.raises(BallparkError, match="REVISION_CONFLICT"):
        validate_revision(before, after, expected_revision=0)


def test_identity_removal_and_domain_change_need_separate_maintenance():
    before = fixture()
    after = copy.deepcopy(before)
    after["revision"] = 2
    after["devices"] = [device(4)]
    with pytest.raises(BallparkError, match="REMOVAL_REQUIRES_MAINTENANCE"):
        validate_revision(before, after, expected_revision=1)
    after = copy.deepcopy(before)
    after.update(revision=2, domain_id=INSTALLATION)
    with pytest.raises(BallparkError, match="DOMAIN_CHANGED"):
        validate_revision(before, after, expected_revision=1)


def test_watchdog_authority_is_separate_from_owner_skill_proposal():
    previous = fixture()
    candidate = copy.deepcopy(previous)
    candidate["revision"] = 2
    proposal = dict(instruction_source="a" * 40, expected_revision=1, candidate=candidate)
    for actor, installation, authorized in [("SKILL", INSTALLATION, True), ("OWNER", INSTALLATION, True),
                                             ("WATCHDOG", DOMAIN, True), ("WATCHDOG", INSTALLATION, False)]:
        with pytest.raises(BallparkError, match="AUTHORITY_REQUIRED|INSTALLATION_MISMATCH"):
            publication_candidate(previous, proposal, actor=actor, installation_id=installation, owner_authorized=authorized)
    result = publication_candidate(previous, proposal, actor="WATCHDOG", installation_id=INSTALLATION, owner_authorized=True)
    assert result["revision"] == 2 and result["visibility"] == "PRIVATE_SHARED"
    assert previous["revision"] == 1  # No storage write, deploy or implicit mutation.


def test_public_schema_artifact_matches_code():
    path = Path(__file__).resolve().parents[2] / "protocol/ballpark.schema.json"
    assert json.loads(path.read_text()) == SCHEMA_BUNDLE


@pytest.mark.parametrize("address", ["not-an-address", "192.0.2.3", "192.0.2.3/99", "fe80::3%private-interface/64"])
def test_invalid_or_interface_scoped_address_has_fixed_diagnostic(address):
    local = fixture()
    local["devices"][0]["interfaces"][0]["addresses"] = [address]
    with pytest.raises(BallparkError, match="BALLPARK_ADDRESS_INVALID") as error:
        validate(local)
    assert address not in str(error.value)


def test_uuid_case_and_alias_newline_cannot_create_ambiguous_identity():
    local = fixture()
    local["devices"][0]["device_id"] = "ABCDEF00-0000-4000-8000-000000000003"
    with pytest.raises(BallparkError, match="IDENTITY_NONCANONICAL"):
        validate(local)
    local = fixture()
    local["devices"][0]["alias"] = "target-a\n"
    with pytest.raises(BallparkError, match="ALIAS_INVALID"):
        validate(local)
