"""Actual native ACTIVE admission and runtime guard through mapped fixed SSH."""
from dataclasses import replace
import sys
from types import SimpleNamespace

import pytest

from tb4.commissioning_checks import detect_environment
from tb4.commissioning_state import Setup, DenyActivation
from tb4.configuration_contract import ConfigurationError, configuration
from tb4.drive.docs_authority import AuthorityError
from tb4.drive.folder_prerequisites import native_folder_prerequisites
from tb4.drive.folder_runtime import NativeFolderCommissioning
from tb4.drive.leadership import Leadership
from tb4.private_settings import SettingsError
from tb4.reconfiguration_admission import AdmissionContext, ConfigurationAdmission
from tb4.reconfiguration_retained import work_sha
from tb4.timing_contract import TimingProfile
from tb4.watchdog.leadership_runtime import Action, Work, NativeWatchdogContext, NativeWatchdogRuntime
from test_folder_candidate_authenticated_ssh import staged, retained
from test_folder_commissioning import context
from test_native_leadership import ACTORS, clock, tid

pytestmark = pytest.mark.skipif(sys.platform != "linux",
    reason="Actual native ACTIVE Folder admission and runtime over fixed SSH")


def active(v):
    s = v.s
    # Existing qualified server-local typed C4 keeps its mapped AFTER checks.
    # Actual selected native capability proof is added to that exact checker.
    s.checker.credentials = v.resolver
    original = s.ctx.setup.store.read()
    assert s.commit.begin(s.checker, owner_authorized=True, decided_at=220) == "PREPARED"
    assert s.commit.advance(s.checker, owner_authorized=True) == "PUBLISHED"
    assert s.promotion.begin(s.checker, owner_authorized=True) == "PREPARED"
    assert s.promotion.advance(s.checker, owner_authorized=True) == "PROFILE_PROMOTED"
    main = s.ctx.setup.store
    assert main.read().previous == original.payload
    checker = native_folder_prerequisites(main, access=v.access,
        environment=lambda:detect_environment(launch_mode="EXTERNAL"),
        source=s.ctx.source, runtime=s.ctx.runtime, clock=lambda:v.now[0], normal_authority=True)
    port = checker.storage.port
    assert type(port) is NativeFolderCommissioning
    payload = main.read().payload
    from tb4.commissioning_state import storage_spec
    _, handle = storage_spec(payload["choices"]["storage"])
    leader = Leadership(port.authority(handle), actor=payload["installation_id"],
        enrollment=s.ctx.leadership.enrollment, profile=TimingProfile.parse(payload["choices"]["timing"]))
    # The original lookup path can be absent after relocation; use the already
    # qualified immutable handle, not a new source-path inspection.
    ctx = AdmissionContext(main, s.ctx.checkpoint, leader, checker, s.ctx.capabilities, s.ctx.clock)
    admission = ConfigurationAdmission(ctx)
    return SimpleNamespace(v=v, main=main, checker=checker, port=port, leader=leader,
        context=ctx, admission=admission)


def runtime(a, calls):
    work = Work(Action.WOL, tid("native-folder-runtime-work"), lambda *_args:calls.append(True) or "COMPLETE")
    ctx = NativeWatchdogContext(a.leader, a.context.checkpoint, a.context.capabilities,
        a.context.clock, lambda:work, configuration_revision=a.admission.revision)
    return NativeWatchdogRuntime(ctx), work


@pytest.mark.parametrize("staged", [False, True], indirect=True)
def test_actual_native_current_admission_after_c4_and_promotion_keeps_work_and_default_denial(staged, capsys):
    v = staged
    a = active(v)
    profile = a.main.read()
    before = a.leader.backend.read().document()
    revision = configuration(before)["revision"]
    assert a.admission.release(owner_authorized=True) == revision
    assert a.admission.revision() == revision
    assert a.leader.profile == TimingProfile.parse(profile.payload["choices"]["timing"])
    assert a.context.checkpoint.read().maintenance is None
    assert a.main.read() == profile and work_sha(a.leader.backend.read().document()) == work_sha(before)
    assert v.port.mapping.select(v.port.expected) == v.current
    assert Setup(a.main).activate(a.checker, DenyActivation())["reason"] == "ACTIVATION_NOT_AUTHORIZED"
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("fault", ["key-permission", "revoked", "forced", "timing"])
def test_actual_current_native_admission_refuses_work_after_late_loss_without_receipt_or_replay(staged, fault):
    a = active(staged)
    assert a.admission.release(owner_authorized=True) == 2
    calls = []
    runner, work = runtime(a, calls)
    assert runner.tick()
    if fault == "key-permission": a.v.key.chmod(0o644)
    if fault == "revoked":
        current = a.main.read(); payload = current.payload
        payload["credential_image"]["bindings"][a.v.handle]["revoked"] = True
        a.main.save(payload, expected_revision=current.revision)
    if fault == "forced":
        successor = Leadership(a.leader.backend, actor=ACTORS[1],
            enrollment=a.leader.enrollment, profile=a.leader.profile)
        plan = successor.request_force(successor.observe(clock(220)),
            request_id=tid("native-folder-admission-forced"), user_requested=True)
        assert successor.commit(plan, mode="START").outcome == "CONFIRMED"
    if fault == "timing": a.leader.profile = replace(a.leader.profile, control_s=7, lease_stale_s=180)
    before, profile = a.context.checkpoint.read(), a.main.read()
    expected = {"key-permission":"HELPER_UNAVAILABLE", "revoked":"HELPER_UNAVAILABLE",
                "forced":"OWNER_SUPERSEDED", "timing":"ADMISSION_TIMING"}[fault]
    with pytest.raises((AuthorityError, ConfigurationError, SettingsError), match="^" + expected + "$"):
        a.admission.revision()
    with pytest.raises((AuthorityError, ConfigurationError, SettingsError), match="^" + expected + "$"):
        runner.perform(work)
    assert not calls and a.context.checkpoint.read() == before and a.main.read() == profile
