"""Actual protected setup and pinned instruction loader; synthetic service/data."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from tb4.ballpark import BallparkError
from tb4.ballpark_setup import GUIDANCE, GuidedBallpark
from tb4.commissioning_state import Setup, validated
from tb4.instructions import InstructionError
from tb4.private_settings import PrivateSettings, SettingsError
from tests.coach.test_instruction_selection import SourceFixture, FACTS, FIRST, SECOND, digest
from test_discovery_workflow import build, observation, CANARY


def source():
    value = SourceFixture()
    value.files[FIRST][GUIDANCE] = b"synthetic setup guidance"
    value.catalog["profiles"][0]["files"][GUIDANCE] = digest(value.files[FIRST][GUIDANCE])
    value.save()
    return value


@pytest.fixture
def system():
    discovery, setup, provider, native, kwargs = build()
    discovery.observe((observation(),))
    origin = source()
    guide = GuidedBallpark(setup, source=origin, runtime=FACTS)
    guide.begin()
    return guide, discovery, setup, provider, native, origin


def proposal(guide, *, partial=False):
    question = guide.questions()
    row = dict(device_id=question["targets"][0]["device_id"], roles=["fetcher"])
    if not partial:
        row.update(platform=dict(os="UNKNOWN", architecture="UNKNOWN"),
                   launch_mode={"fetcher": "UNSUPPORTED"}, transports=[])
    return dict(schema_version=1, expected_revision=question["expected_revision"], devices=[row])


def confirm(guide):
    guide.propose(proposal(guide))
    return guide.confirm(topology="FLAT", at=220, owner_authorized=True)


def test_blank_deployment_has_no_machine_seed_or_implicit_scan():
    discovery, setup, provider, native, kwargs = build()
    guide = GuidedBallpark(setup, source=source(), runtime=FACTS)
    before = provider.store.commits
    assert guide.begin()["targets"] == []
    assert guide.questions()["target_selection_required"]
    with pytest.raises(BallparkError, match="CHOICES_INCOMPLETE"):
        guide.confirm(topology="ISOLATED", at=220, owner_authorized=True)
    assert provider.store.commits == before and setup.private_choices()["descriptor"] is None


def test_partial_choices_restart_request_only_missing_and_never_expose_hints(system):
    guide, discovery, setup, provider, native, origin = system
    result = guide.propose(proposal(guide, partial=True))
    assert result["targets"][0]["missing"] == ["launch_mode", "platform", "transports"]
    restarted = GuidedBallpark(Setup(PrivateSettings(native)), source=origin, runtime=FACTS)
    assert restarted.begin() == result
    assert restarted.setup.private_choices()["descriptor"] is None
    assert all(c not in json.dumps(result) for c in (CANARY, "192.0.2.8", "synthetic-interface", "synthetic-hint"))
    with pytest.raises(BallparkError, match="CHOICES_INCOMPLETE"):
        restarted.confirm(topology="FLAT", at=220, owner_authorized=True)


def test_exact_owner_decision_stages_private_descriptor_without_any_shared_write(system):
    guide, discovery, setup, provider, native, origin = system
    before = copy.deepcopy(provider.store.document)
    view = confirm(guide)
    draft = setup._payload["ballpark_draft"]
    assert view["status"] == "STAGED_UNPUBLISHED"
    assert draft["candidate"]["revision"] == 1
    assert draft["decision"]["kind"] == "LOCAL_OWNER_CONFIRMATION"
    assert draft["pin"]["commit"] == FIRST
    assert setup.private_choices()["descriptor"] is None and provider.store.document == before
    for fact in view["descriptor"]["devices"][0]["capabilities"].values():
        assert fact == {"value": "UNKNOWN", "freshness": "UNKNOWN"}
    public = json.dumps(view) + json.dumps(guide.questions())
    for private in (CANARY, setup.installation_id, "192.0.2.8", "synthetic-interface", "synthetic-hint"):
        assert private not in public
    assert draft["candidate"]["devices"][0]["interfaces"] == []


@pytest.mark.parametrize("field,value", [
    ("credential", "SYNTHETIC_SECRET"), ("interfaces", [{"address": "192.0.2.8"}]),
    ("capabilities", {"fetcher_execution": "SUPPORTED"}), ("command", "run-device-text"),
    ("instructions", "https://invalid.example/instructions"), ("owner_authorized", True),
    ("alias", "pretend-identity"), ("display_name", CANARY),
], ids=["credential", "topology", "capability", "command", "instructions", "authority", "alias", "name"])
def test_untrusted_proposal_cannot_inject_private_data_instructions_or_authority(system, field, value):
    guide, discovery, setup, *_ = system
    candidate = proposal(guide)
    candidate["devices"][0][field] = value
    before = copy.deepcopy(setup._payload)
    with pytest.raises(BallparkError, match="SCHEMA_INVALID") as error:
        guide.propose(candidate)
    assert CANARY not in str(error.value) and setup._payload == before


@pytest.mark.parametrize("kind", ["schema", "revision", "identity", "duplicate", "launch", "role"])
def test_invalid_closed_selection_preserves_draft(system, kind):
    guide, discovery, setup, *_ = system
    value = proposal(guide)
    if kind == "schema": value["schema_version"] = 2
    if kind == "revision": value["expected_revision"] = 99
    if kind == "identity": value["devices"][0]["device_id"] = setup.installation_id
    if kind == "duplicate": value["devices"] *= 2
    if kind == "launch": value["devices"][0]["launch_mode"] = {"watchdog": "OS_SERVICE"}
    if kind == "role": value["devices"][0]["roles"] = ["administrator"]
    before = copy.deepcopy(setup._payload)
    with pytest.raises(BallparkError): guide.propose(value)
    assert setup._payload == before


def test_proposal_is_never_owner_approval(system):
    guide, discovery, setup, *_ = system
    guide.propose(proposal(guide))
    with pytest.raises(BallparkError, match="AUTHORITY_REQUIRED"):
        guide.confirm(topology="FLAT", at=220)
    assert setup._payload["ballpark_draft"]["decision"] is None


@pytest.mark.parametrize("boundary", ["propose", "confirm", "restart"])
def test_revoked_guidance_blocks_new_changes_and_preserves_draft(system, boundary):
    guide, discovery, setup, provider, native, origin = system
    if boundary == "confirm": guide.propose(proposal(guide))
    before = copy.deepcopy(setup._payload)
    origin.catalog["profiles"][0]["status"] = "REVOKED"
    origin.save()
    with pytest.raises(InstructionError, match="RELEASE_WITHDRAWN"):
        if boundary == "propose": guide.propose(proposal(guide))
        elif boundary == "confirm": guide.confirm(topology="FLAT", at=220, owner_authorized=True)
        else: GuidedBallpark(Setup(PrivateSettings(native)), source=origin, runtime=FACTS).begin()
    assert setup._payload == before


def test_restart_keeps_original_pin_when_main_advances_and_rejects_changed_bytes(system):
    guide, discovery, setup, provider, native, origin = system
    origin.advance()
    restarted = GuidedBallpark(Setup(PrivateSettings(native)), source=origin, runtime=FACTS)
    restarted.begin()
    assert restarted.pin.commit == FIRST and origin.head == SECOND
    origin.files[FIRST][GUIDANCE] = b"changed bytes"
    with pytest.raises(BallparkError, match="PIN_HASH"):
        GuidedBallpark(Setup(PrivateSettings(native)), source=origin, runtime=FACTS).begin()


def test_unreleased_or_missing_guidance_has_no_fallback():
    discovery, setup, *_ = build()
    origin = source()
    origin.catalog["profiles"][0]["status"] = "UNRELEASED"
    origin.save()
    guide = GuidedBallpark(setup, source=origin, runtime=FACTS)
    with pytest.raises(InstructionError, match="NO_UNIQUE_COMPATIBLE_RELEASE"): guide.begin()
    assert setup._payload.get("ballpark_draft") is None
    origin = SourceFixture()
    with pytest.raises(InstructionError, match="REFERENCE_NOT_PINNED"):
        GuidedBallpark(setup, source=origin, runtime=FACTS).begin()


def test_discovery_change_requires_new_proposal_before_confirmation(system):
    guide, discovery, setup, *_ = system
    guide.propose(proposal(guide))
    discovery.observe((observation(observed_at=221),))
    with pytest.raises(BallparkError, match="DISCOVERY_CHANGED"):
        guide.confirm(topology="FLAT", at=221, owner_authorized=True)
    guide.propose(proposal(guide))
    guide.confirm(topology="FLAT", at=221, owner_authorized=True)


def test_cancel_restart_resume_and_rollback_cannot_erase_owner_decision(system):
    guide, discovery, setup, provider, native, origin = system
    view = confirm(guide)
    draft = copy.deepcopy(setup._payload["ballpark_draft"])
    with pytest.raises(SettingsError, match="ROLLBACK_UNSAFE"):
        setup.rollback_choices(stopped=True)
    setup.cancel()
    restarted = GuidedBallpark(Setup(PrivateSettings(native)), source=origin, runtime=FACTS)
    with pytest.raises(BallparkError, match="CANCELLED"): restarted.begin()
    restarted.setup.resume()
    restarted.begin()
    assert restarted.view(now=220) == view
    assert restarted.setup._payload["ballpark_draft"] == draft
    with pytest.raises(BallparkError, match="ALREADY_STAGED"): restarted.propose(proposal(restarted))


@pytest.mark.parametrize("field", ["domain", "root", "schema", "decision", "candidate", "authority", "provenance"])
def test_protected_frame_rejects_wrong_binding_or_tampered_draft(system, field):
    guide, discovery, setup, *_ = system
    confirm(guide)
    value = copy.deepcopy(setup._payload)
    draft = value["ballpark_draft"]
    if field == "domain": draft["candidate"]["domain_id"] = setup.installation_id
    if field == "root": value["choices"]["storage"]["authority"]["object_id"] = "wrong-root"
    if field == "schema": draft["schema_version"] = 2
    if field == "decision": draft["decision"]["candidate_digest"] = "0"*64
    if field == "candidate": draft["candidate"]["devices"][0]["alias"] = "different"
    if field == "authority": draft["authority"]["object_id"] = "wrong-authority"
    if field == "provenance": draft["pin"]["commit"] = "main"
    with pytest.raises(SettingsError): validated(value)


def test_unconfirmed_operation_blocks_staging(system):
    guide, discovery, setup, *_ = system
    setup.perform_once("d"*64, lambda: None, owner_authorized=True)
    with pytest.raises(BallparkError, match="INSPECT_REQUIRED"): guide.propose(proposal(guide))


def test_existing_descriptor_remains_active_and_choices_cannot_bypass_draft(system):
    guide, discovery, setup, *_ = system
    confirm(guide)
    active = copy.deepcopy(setup._payload["ballpark_draft"]["candidate"])
    # A previously accepted descriptor is fixture setup, never a runtime activation.
    value = copy.deepcopy(setup._payload)
    del value["ballpark_draft"]
    value["choices"]["descriptor"] = active
    setup._save(value)
    next_guide = GuidedBallpark(setup, source=source(), runtime=FACTS)
    next_guide.begin()
    assert confirm(next_guide)["descriptor"]["revision"] == 2
    assert setup.private_choices()["descriptor"] == active
    with pytest.raises(SettingsError, match="BINDING_FROZEN"):
        setup.choose({"descriptor": setup._payload["ballpark_draft"]["candidate"]})


def test_repository_profile_remains_unreleased_and_hashes_include_setup_guidance():
    root = Path(__file__).resolve().parents[2]
    catalog = json.loads((root / "skill/tb4/compatibility.json").read_text(encoding="utf-8"))
    profile = catalog["profiles"][0]
    assert profile["status"] == "UNRELEASED" and profile["builds"] == []
    assert GUIDANCE in profile["files"]
    for path, expected in profile["files"].items():
        assert hashlib.sha256((root / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == expected
