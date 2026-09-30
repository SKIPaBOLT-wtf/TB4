"""Unreleased RP-011 timing specification; no wall-clock, network or runtime IO.

Callers supply clock samples and already commissioned capabilities. This model
does not qualify real latency, provider quotas or OS suspend-clock behavior.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math


OWNER = dict(watchdog_network_fast_s=60, watchdog_network_slow_s=600,
             watchdog_idle_after_s=3600, fetcher_fast_s=20,
             fetcher_slow_s=1200, fetcher_idle_after_s=1200)
MAX_SEQUENCE = 2**63 - 1


class TimingError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise TimingError(code)


def number(value, low=0, high=10**12):
    return type(value) in {int, float} and math.isfinite(value) and low <= value <= high


@dataclass(frozen=True)
class TimingProfile:
    watchdog_network_fast_s: int = 60
    watchdog_network_slow_s: int = 600
    watchdog_idle_after_s: int = 3600
    fetcher_fast_s: int = 20
    fetcher_slow_s: int = 1200
    fetcher_idle_after_s: int = 1200
    inbox_s: int = 5
    control_s: int = 5
    watchdog_heartbeat_s: int = 30
    fetcher_heartbeat_s: int = 120
    fetcher_fresh_s: int = 300
    lease_renew_s: int = 20
    lease_stale_s: int = 120
    standby_s: int = 10
    local_supervision_s: float = 0.25
    visibility_s: int = 10
    transport_queue_s: int = 30
    skew_s: int = 10
    publication_wait_s: int = 120
    idle_policy: str = "SLOW"
    launcher_kind: str | None = None
    launcher_bound_s: int | None = None

    def __post_init__(self):
        values = asdict(self)
        for key, value in OWNER.items():
            require(type(values[key]) is int and values[key] == value, "OWNER_CADENCE")
        for key in ("inbox_s", "control_s", "watchdog_heartbeat_s", "fetcher_heartbeat_s",
                    "fetcher_fresh_s", "lease_renew_s", "lease_stale_s", "standby_s",
                    "visibility_s", "transport_queue_s", "skew_s", "publication_wait_s"):
            require(type(values[key]) is int and 1 <= values[key] <= 86400, "PROFILE_RANGE")
        require(number(self.local_supervision_s, 0.01, 1), "PROFILE_RANGE")
        require(type(self.idle_policy) is str and self.idle_policy in {"SLOW", "EXIT"}, "IDLE_POLICY")
        require(self.launcher_kind is None or (type(self.launcher_kind) is str
                and self.launcher_kind in {"SSH", "OS_SERVICE", "EXTERNAL"}), "LAUNCHER_KIND")
        require((self.launcher_kind is None) == (self.launcher_bound_s is None), "LAUNCHER_BOUND")
        if self.launcher_bound_s is not None:
            require(type(self.launcher_bound_s) is int and 1 <= self.launcher_bound_s <= 86400, "LAUNCHER_BOUND")
        slack = self.visibility_s + self.transport_queue_s + 2 * self.skew_s
        require(self.lease_stale_s > max(self.lease_renew_s, self.watchdog_heartbeat_s) + slack, "LEASE_TOO_SHORT")
        require(self.fetcher_fresh_s > self.fetcher_heartbeat_s + slack, "FRESHNESS_TOO_SHORT")
        require(self.publication_wait_s > slack, "PUBLICATION_TOO_SHORT")

    @classmethod
    def parse(cls, value):
        require(type(value) is dict and set(value) == set(asdict(cls())), "PROFILE_SHAPE")
        return cls(**value)


class ActivityClock:
    """Age since a genuinely new scoped accepted-command sequence.

    The sequence is committed alongside admission (global for WATCHDOG, target
    generation for FETCHER). Heartbeats, reads and retries do not advance it.
    Persist this image on changes/shutdown; loading it never sets activity to now.
    """
    def __init__(self, monotonic, utc, *, saved=None, new_installation=False, elapsed_wall_trusted=False, skew_s=10):
        require(number(monotonic) and number(utc) and type(skew_s) is int and 0 <= skew_s <= 86400
                and type(new_installation) is bool and type(elapsed_wall_trusted) is bool, "CLOCK_SAMPLE")
        require((saved is None and new_installation) or (saved is not None and not new_installation), "ACTIVITY_RECOVERY_REQUIRED")
        self.monotonic, self.utc, self.skew_s = monotonic, utc, skew_s
        self._anchor_monotonic, self._anchor_utc = monotonic, utc
        self.age_s, self.sequence, self.known = 0.0, 0, True
        if saved is not None:
            require(type(saved) is dict and set(saved) == {"schema_version", "age_s", "sequence", "checkpoint_utc", "clock_known"}, "ACTIVITY_IMAGE")
            require(type(saved["schema_version"]) is int and saved["schema_version"] == 1
                    and number(saved["age_s"]) and number(saved["checkpoint_utc"])
                    and type(saved["sequence"]) is int and 0 <= saved["sequence"] <= MAX_SEQUENCE
                    and type(saved["clock_known"]) is bool, "ACTIVITY_IMAGE")
            self.age_s, self.sequence = saved["age_s"], saved["sequence"]
            elapsed = utc - saved["checkpoint_utc"]
            self.known = bool(elapsed_wall_trusted and elapsed >= -skew_s)
            if self.known:
                self.age_s = min(10**12, self.age_s + max(0, elapsed))

    def sample(self, monotonic, utc, *, elapsed_wall_trusted=False):
        require(number(monotonic) and number(utc) and type(elapsed_wall_trusted) is bool, "CLOCK_SAMPLE")
        require(monotonic >= self.monotonic, "MONOTONIC_REVERSED")
        elapsed, wall = monotonic - self.monotonic, utc - self.utc
        if elapsed_wall_trusted and wall >= -self.skew_s:
            self.age_s = min(10**12, self.age_s + max(elapsed, wall, 0))
            self.known = True
            self._anchor_monotonic, self._anchor_utc = monotonic, utc
        else:
            self.age_s = min(10**12, self.age_s + elapsed)
            drift = (utc - self._anchor_utc) - (monotonic - self._anchor_monotonic)
            self.known = self.known and abs(drift) <= self.skew_s
        self.monotonic, self.utc = monotonic, utc
        return self.age_s

    def accepted(self, sequence):
        require(type(sequence) is int and 1 <= sequence <= MAX_SEQUENCE, "ACTIVITY_SEQUENCE")
        if sequence <= self.sequence:
            return False
        self.sequence, self.age_s = sequence, 0.0
        # Acceptance anchors fresh local monotonic time, but does not repair UTC.
        return True

    def checkpoint(self):
        return dict(schema_version=1, age_s=self.age_s, sequence=self.sequence,
                    checkpoint_utc=self.utc, clock_known=self.known)


def modes(profile, watchdog_activity, fetcher_activity, *, pending=False, executing=False, publication=False, unread=False, unknown=False):
    require(isinstance(profile, TimingProfile) and isinstance(watchdog_activity, ActivityClock)
            and isinstance(fetcher_activity, ActivityClock), "PROFILE_SHAPE")
    activity = fetcher_activity
    holds = (pending, executing, publication, unread, unknown)
    require(all(type(v) is bool for v in holds), "HOLD_SHAPE")
    # Network observation has its own owner threshold even during long work.
    network = profile.watchdog_network_fast_s if not watchdog_activity.known or watchdog_activity.age_s < profile.watchdog_idle_after_s else profile.watchdog_network_slow_s
    if any(holds):
        fetcher, poll = "BUSY", profile.fetcher_fast_s
    elif not activity.known:
        fetcher, poll = "HOLD_CLOCK", profile.fetcher_fast_s
    elif activity.age_s < profile.fetcher_idle_after_s:
        fetcher, poll = "ACTIVE", profile.fetcher_fast_s
    elif profile.idle_policy == "SLOW":
        fetcher, poll = "SLOW", profile.fetcher_slow_s
    else:
        fetcher, poll = "EXITED", None
    return dict(network_s=network, fetcher_mode=fetcher, fetcher_poll_s=poll,
                clock_known=activity.known, activity_sequence=activity.sequence,
                network_clock_known=watchdog_activity.known, watchdog_activity_sequence=watchdog_activity.sequence)


def claim_budget(profile, *, fetcher_mode, route_fresh=False):
    require(isinstance(profile, TimingProfile) and type(route_fresh) is bool, "PROFILE_SHAPE")
    require(type(fetcher_mode) is str and fetcher_mode in {"ACTIVE", "BUSY", "SLOW", "EXITED", "HOLD_CLOCK"}, "MODE")
    require(fetcher_mode != "HOLD_CLOCK", "CLOCK_UNQUALIFIED")
    routes = []
    if fetcher_mode in {"ACTIVE", "BUSY", "HOLD_CLOCK"}:
        routes.append(profile.fetcher_fast_s)
    elif fetcher_mode == "SLOW":
        routes.append(profile.fetcher_slow_s)
    if route_fresh and profile.launcher_bound_s is not None:
        routes.append(profile.launcher_bound_s + profile.fetcher_fast_s)
    require(routes, "MANUAL_START_REQUIRED")
    return profile.inbox_s + min(routes) + profile.visibility_s + profile.transport_queue_s + 2 * profile.skew_s + 1


def validate_deadlines(profile, *, fetcher_mode, claim_ttl_s, run_limit_s,
                       publication_wait_s, ack_recycle_after_s=None, route_fresh=False):
    for value in (claim_ttl_s, run_limit_s, publication_wait_s):
        require(type(value) is int and 1 <= value <= 86400, "DEADLINE_RANGE")
    require(claim_ttl_s >= claim_budget(profile, fetcher_mode=fetcher_mode, route_fresh=route_fresh), "CLAIM_TOO_SHORT")
    require(publication_wait_s >= profile.publication_wait_s, "PUBLICATION_TOO_SHORT")
    require(ack_recycle_after_s is None, "ACK_CANNOT_EXPIRE_TO_RECYCLE")
    return dict(claim_ttl_s=claim_ttl_s, run_limit_s=run_limit_s,
                publication_wait_s=publication_wait_s, ack_recycle_after_s=None)


class ClockSet:
    """Independent periodic clocks; no catch-up burst after a long suspension."""
    def __init__(self, profile, now=0):
        require(isinstance(profile, TimingProfile) and number(now), "CLOCK_SAMPLE")
        self.intervals = dict(network=profile.watchdog_network_fast_s,
            inbox=profile.inbox_s, fetcher_poll=profile.fetcher_fast_s,
            control=profile.control_s, watchdog_heartbeat=profile.watchdog_heartbeat_s,
            fetcher_heartbeat=profile.fetcher_heartbeat_s, lease=profile.lease_renew_s,
            standby=profile.standby_s, supervision=profile.local_supervision_s)
        self.base_intervals = self.intervals.copy()
        self.intervals.update(control=None, supervision=None)
        self.due_at = {key:None if period is None else now + period for key,period in self.intervals.items()}
        self.last_now = now

    def _sample(self, now):
        require(number(now) and now >= self.last_now, "MONOTONIC_REVERSED")
        self.last_now = now

    def due(self, now):
        self._sample(now)
        return tuple(key for key,deadline in self.due_at.items() if deadline is not None and now >= deadline)

    def completed(self, name, now):
        require(name in self.intervals and self.due_at[name] is not None, "CLOCK_NAME")
        self._sample(now)
        # At most one completion; missed intervals are not replayed.
        self.due_at[name] = now + self.intervals[name]

    def set_modes(self, state, now):
        expected = {"network_s", "fetcher_mode", "fetcher_poll_s", "clock_known", "activity_sequence",
                    "network_clock_known", "watchdog_activity_sequence"}
        require(type(state) is dict and set(state) == expected, "MODE")
        mode = state["fetcher_mode"]
        periods = {"ACTIVE":20, "BUSY":20, "HOLD_CLOCK":20, "SLOW":1200, "EXITED":None}
        require(type(mode) is str and mode in periods and state["fetcher_poll_s"] == periods[mode]
                and type(state["network_s"]) is int and state["network_s"] in {60,600}
                and (state["fetcher_poll_s"] is None or type(state["fetcher_poll_s"]) is int)
                and type(state["clock_known"]) is bool
                and type(state["network_clock_known"]) is bool
                and type(state["watchdog_activity_sequence"]) is int and 0 <= state["watchdog_activity_sequence"] <= MAX_SEQUENCE
                and type(state["activity_sequence"]) is int and 0 <= state["activity_sequence"] <= MAX_SEQUENCE, "MODE")
        self._sample(now)
        changes = {"network":state["network_s"], "fetcher_poll":state["fetcher_poll_s"],
            "fetcher_heartbeat":None if mode == "EXITED" else self.base_intervals["fetcher_heartbeat"],
            "control":self.base_intervals["control"] if mode == "BUSY" else None,
            "supervision":self.base_intervals["supervision"] if mode == "BUSY" else None}
        for key, period in changes.items():
            self.intervals[key] = period
            if period is None:
                self.due_at[key] = None
            else:
                old = self.due_at[key]
                self.due_at[key] = now + period if old is None else min(old, now + period)


def effective_profile(profile, state, clocks, *, utc, monotonic, route_fresh=False):
    require(number(utc) and number(monotonic) and type(route_fresh) is bool, "CLOCK_SAMPLE")
    due = clocks.due_at["fetcher_poll"]
    next_check = None if not state["clock_known"] or due is None else utc + max(0, due - monotonic)
    try:
        require(state["clock_known"], "CLOCK_UNQUALIFIED")
        budget = claim_budget(profile, fetcher_mode=state["fetcher_mode"], route_fresh=route_fresh)
        availability = "AUTOMATIC_ROUTE"
    except TimingError as error:
        require(str(error) in {"MANUAL_START_REQUIRED", "CLOCK_UNQUALIFIED"}, "MODE")
        budget, availability = None, str(error)
    return dict(compatibility_status="UNRELEASED", **asdict(profile), **state,
                next_fetcher_check_utc=next_check, minimum_claim_ttl_s=budget,
                delivery=availability, launcher_route_fresh=route_fresh)


def quota_budget(profile, *, active, slow, busy, exited=0, standbys=1,
                 reads_per_minute=300, writes_per_minute=60,
                 read_reserve=30, write_reserve=12, retry_factor=1.25):
    """Conservative average request estimate, NOT burst/contention qualification.

    Count poll/control reads independently and a fresh read for every heartbeat
    and lease write. No network probe is itself a document request. Reserve is
    explicit headroom for admission, result/ACK and summaries; enforce at runtime.
    """
    require(isinstance(profile, TimingProfile), "PROFILE_SHAPE")
    require(all(type(v) is int and 0 <= v <= 64 for v in (active,slow,busy,exited,standbys))
            and 1 <= active + slow + busy + exited <= 64, "POPULATION")
    require(all(number(v, 1) for v in (reads_per_minute,writes_per_minute,read_reserve,write_reserve))
            and number(retry_factor, 1, 10), "QUOTA_RANGE")
    present = active + slow + busy
    writes = (60 / profile.watchdog_heartbeat_s + 60 / profile.lease_renew_s
              + present * 60 / profile.fetcher_heartbeat_s)
    reads = (60 / profile.inbox_s + standbys * 60 / profile.standby_s + writes
             + (active + busy) * 60 / profile.fetcher_fast_s
             + slow * 60 / profile.fetcher_slow_s + busy * 60 / profile.control_s)
    needed_reads, needed_writes = reads * retry_factor + read_reserve, writes * retry_factor + write_reserve
    require(needed_reads <= reads_per_minute and needed_writes <= writes_per_minute, "QUOTA_INFEASIBLE")
    return dict(reads_per_minute=needed_reads, writes_per_minute=needed_writes,
                read_reserve=read_reserve, write_reserve=write_reserve,
                qualification="AVERAGE_ESTIMATE_ONLY")
