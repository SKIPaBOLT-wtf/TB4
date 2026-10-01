"""Allowlisted actual local FETCHER reports; neither a profile nor presence grants work."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import re
import shutil
import sys

from .commissioning_checks import Environment, detect_environment
from .timing_contract import TimingProfile, ActivityClock, modes

INTERPRETERS = ("python", "python3", "pwsh", "powershell", "bash", "sh")
INTERPRETER_STATES = ("UNAVAILABLE", "DISABLED", "ENABLED", "UNQUALIFIED")
OPERATING_SYSTEMS = ("WINDOWS", "LINUX", "OTHER")
ARCHITECTURES = ("X64", "ARM64", "X86", "OTHER")
LAUNCH_MODES = ("DESKTOP_SESSION", "OS_SERVICE", "EXTERNAL")
MODES = ("ACTIVE", "SLOW", "BUSY", "HOLD_CLOCK", "EXITED")
FEATURES = ("inline_commands", "script_artifacts")


class EnrollmentError(ValueError):
    """Fixed codes only, never a raw profile, private binding or provider error."""


def require(ok, code):
    if not ok:
        raise EnrollmentError(code)


def integer(value, low=0, high=10**12):
    return type(value) is int and low <= value <= high


def version(value):
    return (value is None or type(value) is list and len(value) == 3
            and all(integer(v, 0, 65535) for v in value))


@dataclass(frozen=True, repr=False)
class RuntimeSnapshot:
    environment: Environment
    interpreters: dict
    capabilities: dict
    build_commit: str
    timing: TimingProfile = field(default_factory=TimingProfile)


def native_snapshot(*, launch_mode, build_commit, disabled=frozenset(), features=frozenset(), timing=None):
    """Entrypoint supplies actual launch mode and fixed executor configuration.

    The running nonfrozen CPython is proven. PATH presence for other named binaries
    is only UNQUALIFIED; no arbitrary discovered binary is executed. A frozen
    program is not automatically an external Python interpreter. Paths stay local.
    """
    require(type(disabled) is frozenset and disabled <= set(INTERPRETERS)
            and type(features) is frozenset and features <= set(FEATURES), "PROFILE_CONFIGURATION")
    environment = detect_environment(launch_mode=launch_mode)
    evidence = {}
    for name in INTERPRETERS:
        running = name == "python" and not getattr(sys, "frozen", False)
        present = running or shutil.which(name) is not None
        state = ("UNAVAILABLE" if not present else "DISABLED" if name in disabled
                 else "ENABLED" if running else "UNQUALIFIED")
        evidence[name] = dict(state=state, version=list(sys.version_info[:3]) if running else None)
    effective = TimingProfile() if timing is None else timing
    require(type(effective) is TimingProfile, "PROFILE_CONFIGURATION")
    return RuntimeSnapshot(environment, evidence,
                           {name: name in features for name in FEATURES}, build_commit, effective)


def report(snapshot, profile, activity, *, revision, observed_at, holds=None):
    require(type(snapshot) is RuntimeSnapshot and type(snapshot.environment) is Environment
            and type(profile) is TimingProfile and type(activity) is ActivityClock,
            "PROFILE_CONTEXT")
    require(integer(observed_at) and observed_at == int(activity.utc), "PROFILE_CLOCK")
    holds = {} if holds is None else holds
    require(type(holds) is dict and set(holds) <= {
        "pending", "executing", "publication", "unread", "unknown"}
        and all(type(v) is bool for v in holds.values()), "PROFILE_HOLDS")
    effective = modes(profile, activity, activity, **holds)
    env = snapshot.environment
    value = dict(schema_version=1, revision=revision, build_commit=snapshot.build_commit,
        platform=dict(os=env.os, architecture=env.architecture), launch_mode=env.launch_mode,
        interpreters=copy.deepcopy(snapshot.interpreters), capabilities=copy.deepcopy(snapshot.capabilities),
        timing=dict(fast_s=profile.fetcher_fast_s, slow_s=profile.fetcher_slow_s,
                    idle_after_s=profile.fetcher_idle_after_s, idle_policy=profile.idle_policy,
                    heartbeat_s=profile.fetcher_heartbeat_s, fresh_s=profile.fetcher_fresh_s,
                    launcher_kind=profile.launcher_kind, launcher_bound_s=profile.launcher_bound_s),
        polling=dict(mode=effective["fetcher_mode"], poll_s=effective["fetcher_poll_s"],
                     observed_at=observed_at, clock_known=activity.known,
                     next_check_at=None if effective["fetcher_poll_s"] is None
                     else observed_at + effective["fetcher_poll_s"]))
    return validate(value)


def validate(value):
    try:
        require(type(value) is dict and set(value) == {"schema_version", "revision", "build_commit",
            "platform", "launch_mode", "interpreters", "capabilities", "timing", "polling"}
            and type(value["schema_version"]) is int and value["schema_version"] == 1
            and integer(value["revision"], 1, 2**63-1)
            and type(value["build_commit"]) is str and re.fullmatch(r"[0-9a-f]{40}", value["build_commit"]),
            "PROFILE_SCHEMA")
        platform = value["platform"]
        require(type(platform) is dict and set(platform) == {"os", "architecture"}
                and platform["os"] in OPERATING_SYSTEMS and platform["architecture"] in ARCHITECTURES
                and value["launch_mode"] in LAUNCH_MODES, "PROFILE_PLATFORM")
        evidence = value["interpreters"]
        require(type(evidence) is dict and set(evidence) == set(INTERPRETERS), "PROFILE_INTERPRETERS")
        for info in evidence.values():
            require(type(info) is dict and set(info) == {"state", "version"}
                    and info["state"] in INTERPRETER_STATES and version(info["version"])
                    and (info["state"] != "ENABLED" or info["version"] is not None)
                    and (info["state"] != "UNAVAILABLE" or info["version"] is None), "PROFILE_INTERPRETERS")
        features = value["capabilities"]
        require(type(features) is dict and set(features) == set(FEATURES)
                and all(type(v) is bool for v in features.values())
                and (not any(features.values()) or any(i["state"] == "ENABLED" for i in evidence.values())),
                "PROFILE_CAPABILITIES")
        timing = value["timing"]
        require(type(timing) is dict and set(timing) == {"fast_s", "slow_s", "idle_after_s", "idle_policy",
                "heartbeat_s", "fresh_s", "launcher_kind", "launcher_bound_s"}, "PROFILE_TIMING")
        require(type(timing["fast_s"]) is int and timing["fast_s"] == 20
                and type(timing["slow_s"]) is int and timing["slow_s"] == 1200
                and type(timing["idle_after_s"]) is int and timing["idle_after_s"] == 1200, "PROFILE_TIMING")
        TimingProfile(fetcher_heartbeat_s=timing["heartbeat_s"], fetcher_fresh_s=timing["fresh_s"],
                      idle_policy=timing["idle_policy"], launcher_kind=timing["launcher_kind"],
                      launcher_bound_s=timing["launcher_bound_s"])
        polling = value["polling"]
        require(type(polling) is dict and set(polling) == {
            "mode", "poll_s", "observed_at", "clock_known", "next_check_at"}
            and polling["mode"] in MODES and integer(polling["observed_at"])
            and type(polling["clock_known"]) is bool, "PROFILE_POLLING")
        expected = None if polling["mode"] == "EXITED" else 1200 if polling["mode"] == "SLOW" else 20
        require((expected is None and polling["poll_s"] is None and polling["next_check_at"] is None)
                or type(polling["poll_s"]) is int and polling["poll_s"] == expected
                and integer(polling["next_check_at"])
                and polling["next_check_at"] == polling["observed_at"] + expected, "PROFILE_POLLING")
        require(polling["mode"] not in {"SLOW", "EXITED"} or polling["clock_known"], "PROFILE_POLLING")
        require(polling["mode"] != "SLOW" or timing["idle_policy"] == "SLOW", "PROFILE_POLLING")
        require(polling["mode"] != "EXITED" or timing["idle_policy"] == "EXIT", "PROFILE_POLLING")
        return copy.deepcopy(value)
    except EnrollmentError:
        raise
    except Exception:
        raise EnrollmentError("PROFILE_SCHEMA") from None


def compact(value, enrollment_revision):
    value = validate(value)
    require(integer(enrollment_revision, 1, 2**63-1), "ENROLLMENT_REVISION")
    t, p = value["timing"], value["polling"]
    return [1, enrollment_revision, value["revision"], value["build_commit"],
            OPERATING_SYSTEMS.index(value["platform"]["os"]), ARCHITECTURES.index(value["platform"]["architecture"]),
            LAUNCH_MODES.index(value["launch_mode"]),
            [[INTERPRETER_STATES.index(value["interpreters"][n]["state"]), value["interpreters"][n]["version"]]
             for n in INTERPRETERS], [int(value["capabilities"][n]) for n in FEATURES],
            [int(t["idle_policy"] == "EXIT"), t["heartbeat_s"], t["fresh_s"], t["launcher_kind"], t["launcher_bound_s"]],
            [MODES.index(p["mode"]), p["observed_at"], int(p["clock_known"])]]


def expand(value, enrollment_revision):
    try:
        require(type(value) is list and len(value) == 11 and type(value[0]) is int and value[0] == 1
                and integer(value[1], 1, 2**63-1) and value[1] == enrollment_revision, "PROFILE_CODEC")
        for index, enum in ((4, OPERATING_SYSTEMS), (5, ARCHITECTURES), (6, LAUNCH_MODES)):
            require(integer(value[index], 0, len(enum)-1), "PROFILE_CODEC")
        require(type(value[7]) is list and len(value[7]) == len(INTERPRETERS)
                and type(value[8]) is list and len(value[8]) == len(FEATURES)
                and all(integer(v, 0, 1) for v in value[8])
                and type(value[9]) is list and len(value[9]) == 5 and integer(value[9][0], 0, 1)
                and type(value[10]) is list and len(value[10]) == 3
                and integer(value[10][0], 0, len(MODES)-1) and integer(value[10][2], 0, 1), "PROFILE_CODEC")
        interpreters = {}
        for name, info in zip(INTERPRETERS, value[7]):
            require(type(info) is list and len(info) == 2 and integer(info[0], 0, len(INTERPRETER_STATES)-1),
                    "PROFILE_CODEC")
            interpreters[name] = dict(state=INTERPRETER_STATES[info[0]], version=info[1])
        t, p = value[9], value[10]
        mode = MODES[p[0]]
        poll = None if mode == "EXITED" else 1200 if mode == "SLOW" else 20
        result = dict(schema_version=1, revision=value[2], build_commit=value[3],
            platform=dict(os=OPERATING_SYSTEMS[value[4]], architecture=ARCHITECTURES[value[5]]),
            launch_mode=LAUNCH_MODES[value[6]], interpreters=interpreters,
            capabilities=dict(zip(FEATURES, map(bool, value[8]))),
            timing=dict(fast_s=20, slow_s=1200, idle_after_s=1200, idle_policy="EXIT" if t[0] else "SLOW",
                        heartbeat_s=t[1], fresh_s=t[2], launcher_kind=t[3], launcher_bound_s=t[4]),
            polling=dict(mode=mode, poll_s=poll, observed_at=p[1], clock_known=bool(p[2]),
                         next_check_at=None if poll is None else p[1]+poll))
        result = validate(result)
        require(compact(result, enrollment_revision) == value, "PROFILE_CODEC")
        return result
    except EnrollmentError:
        raise
    except Exception:
        raise EnrollmentError("PROFILE_CODEC") from None


def freshness(value, now):
    value = validate(value)
    require(integer(now), "PROFILE_CLOCK")
    p = value["polling"]
    if not p["clock_known"] or now < p["observed_at"]:
        return "CLOCK_UNCERTAIN"
    return "FRESH" if now-p["observed_at"] < value["timing"]["fresh_s"] else "STALE"
