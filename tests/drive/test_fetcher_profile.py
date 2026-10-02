"""Actual local runtime facts, clock policy and closed compact profile privacy."""
import copy
import json
import os
import sys

import pytest

from tb4.commissioning_checks import Environment
from tb4.fetcher_profile import (RuntimeSnapshot, native_snapshot, report, validate, compact, expand,
                                freshness, EnrollmentError, INTERPRETERS)
from tb4.timing_contract import TimingProfile, ActivityClock

BUILD = "a"*40
CANARY = "SYNTHETIC_PRIVATE_PROFILE_CANARY"


def snapshot(**changes):
    data = dict(environment=Environment("LINUX", "X64", "USER", "OS_SERVICE", "UNQUALIFIED"),
        interpreters={n: dict(state="ENABLED" if n == "python" else "DISABLED",
                             version=[3,11,9] if n == "python" else None) for n in INTERPRETERS},
        capabilities=dict(inline_commands=True, script_artifacts=False), build_commit=BUILD,
        timing=TimingProfile())
    data.update(changes)
    return RuntimeSnapshot(**data)


def profile(*, revision=1, now=220, activity=None, runtime=None, holds=None):
    activity = activity or ActivityClock(now, now, new_installation=True)
    runtime = runtime or snapshot()
    return report(runtime, runtime.timing, activity, revision=revision, observed_at=now, holds=holds)


def test_native_process_os_python_and_unqualified_path_presence_have_no_private_output(monkeypatch, capsys):
    monkeypatch.setattr("tb4.fetcher_profile.shutil.which", lambda name: CANARY)
    actual = native_snapshot(launch_mode="DESKTOP_SESSION", build_commit=BUILD, disabled=frozenset({"sh"}))
    value = profile(runtime=actual)
    assert value["platform"]["os"] == ("WINDOWS" if os.name == "nt" else "LINUX")
    assert value["interpreters"]["python"] == dict(state="ENABLED", version=list(sys.version_info[:3]))
    assert value["interpreters"]["python3"] == dict(state="UNQUALIFIED", version=None)
    assert value["interpreters"]["sh"] == dict(state="DISABLED", version=None)
    assert value["capabilities"] == dict(inline_commands=False, script_artifacts=False)
    assert all(s not in json.dumps(value) for s in (CANARY, sys.executable))
    assert capsys.readouterr() == ("", "")


def test_frozen_app_is_not_an_external_python_interpreter(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("tb4.fetcher_profile.shutil.which", lambda name: None)
    value = profile(runtime=native_snapshot(launch_mode="EXTERNAL", build_commit=BUILD))
    assert all(i == dict(state="UNAVAILABLE", version=None) for i in value["interpreters"].values())
    assert not any(value["capabilities"].values())


@pytest.mark.parametrize("mode", ["ACTIVE", "SLOW", "BUSY", "HOLD_CLOCK", "EXITED"])
def test_effective_owner_cadence_clock_and_hold_modes_roundtrip(mode):
    timing = TimingProfile(idle_policy="EXIT" if mode == "EXITED" else "SLOW")
    activity = ActivityClock(0, 0, new_installation=True)
    now = 1200 if mode in {"SLOW", "BUSY", "EXITED"} else 20
    activity.sample(now, now)
    if mode == "HOLD_CLOCK":
        activity.known = False
    value = profile(now=now, activity=activity, runtime=snapshot(timing=timing),
                    holds={"unknown":True} if mode == "BUSY" else None)
    assert value["polling"]["mode"] == mode
    assert expand(compact(value, 3), 3) == value
    assert value["timing"]["fast_s"] == 20 and value["timing"]["slow_s"] == 1200
    assert value["polling"]["next_check_at"] == (None if mode == "EXITED" else now+value["polling"]["poll_s"])


def test_future_stale_boundary_and_unknown_clock_never_become_fresh():
    value = profile()
    assert freshness(value, 219) == "CLOCK_UNCERTAIN"
    assert freshness(value, 519) == "FRESH"
    assert freshness(value, 520) == "STALE"
    activity = ActivityClock(220, 220, new_installation=True)
    activity.known = False
    assert freshness(profile(activity=activity), 220) == "CLOCK_UNCERTAIN"


@pytest.mark.parametrize("mutation", ["private-field", "interpreter-path", "unknown-name", "enabled-without-proof",
    "bool-revision", "bool-version", "wrong-cadence", "wrong-next-check", "feature-without-interpreter"])
def test_untrusted_or_inconsistent_profile_is_rejected(mutation):
    value = profile()
    if mutation == "private-field": value["hostname"] = CANARY
    elif mutation == "interpreter-path": value["interpreters"]["python"]["path"] = CANARY
    elif mutation == "unknown-name": value["interpreters"][CANARY] = dict(state="ENABLED", version=[1,0,0])
    elif mutation == "enabled-without-proof": value["interpreters"]["python"]["version"] = None
    elif mutation == "bool-revision": value["revision"] = True
    elif mutation == "bool-version": value["interpreters"]["python"]["version"] = [True,1,0]
    elif mutation == "wrong-cadence": value["timing"]["fast_s"] = 21
    elif mutation == "wrong-next-check": value["polling"]["next_check_at"] += 1
    elif mutation == "feature-without-interpreter": value["interpreters"]["python"]["state"] = "DISABLED"
    with pytest.raises(EnrollmentError): validate(value)


@pytest.mark.parametrize("index,change", [(0,True), (1,True), (4,-1), (7,[]), (8,[True,0]), (9,[True,120,300,None,None]),
    (10,[0,220,True])], ids=["bool-codec", "bool-enrollment", "negative-enum", "missing-interpreters", "bool-feature", "bool-policy", "bool-clock"])
def test_compact_profile_rejects_ambiguous_encoding(index, change):
    value = compact(profile(), 1)
    value[index] = change
    with pytest.raises(EnrollmentError): expand(value, 1)
