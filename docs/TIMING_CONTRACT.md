# R2 timing profiles and relationship validation

RP-011/A001, **UNRELEASED**. `protocol/drafts/r2-timing-profile.json` is the
machine profile; `src/tb4/timing_contract.py` is its pure executable specification.
Installed `config/defaults.toml`, v1 scheduler and services remain unchanged.
R2 runtime wiring belongs to the planned WATCHDOG/FETCHER implementation steps.

## Owner values and activity

| Mechanism | Required seconds |
| --- | ---: |
| WATCHDOG network observation, recent activity | 60 |
| WATCHDOG network observation, idle | 600 |
| No new accepted command before network idle | 3600 |
| FETCHER normal command poll | 20 |
| FETCHER inactivity before SLOW or configured EXIT | 1200 |
| FETCHER command poll in SLOW | 1200 |

These six values are fixed owner requirements. A deployment cannot shorten them
to conceal an incompatible deadline or capacity. Exact equality enters the idle
mode. A genuinely new accepted command refreshes activity. Status reads, GUI
launches, heartbeats, publication retries, repeated submissions and maintenance
do not. A global accepted-command sequence updates WATCHDOG activity atomically
with admission; each FETCHER uses only its target's accepted generation. Commands
to another target do not refresh this FETCHER. Even co-located roles have distinct
activity records. The model requires both role clocks explicitly.

Inactivity age is time since that accepted command, not a timer restarted when
the GUI opens. Pending, executing, unpublished, unread or unknown work holds
FETCHER in BUSY with 20-second command polling; it cannot slow, exit or be reused.
Age continues during the hold. Once all holds clear, an already expired inactivity
threshold can immediately enter SLOW/EXIT; ordinary ACK or cleanup is not new
command activity. A long command does not alter WATCHDOG's independent 3600-second
network-observation threshold. Control, heartbeat, lease and process supervision
remain independent of network and slow command polling.

## Persistent time and suspend/restart

The durable activity image stores sequence, age, checkpoint UTC and clock-quality
state. Checkpointing never resets age. Monotonic values belong to one process/boot
and are not persisted as cross-boot timestamps. A new installation requires an
explicit initialization flag; missing prior state requires recovery, not a fabricated
fresh activity time. Recover sequence/age from validated local/shared admission
records before normal idle decisions.

Within one process, use monotonic elapsed time. Compare UTC drift to the whole
interval since the last qualified anchor, preventing small repeated wall changes
from hiding cumulative skew. Backward monotonic samples fail without mutation.
On restart or a platform whose monotonic clock pauses during suspend, add wall
elapsed time only when that elapsed interval is independently qualified. Otherwise
retain the known age floor and HOLD_CLOCK: poll conservatively, expose uncertainty,
and do not automatically exit or promise a UTC claim deadline. A qualified later
sample may restore timing confidence; unknown elapsed time is never invented.
Age saturates at the representable maximum rather than wrapping into recent activity.

The trust flag in a test is an explicit assumption, not a capability granted to
an arbitrary caller. Production OS clock/suspend adapters and trusted skew calibration
must qualify it. This idle-clock hold is not a new WATCHDOG takeover barrier:
RP-008 A-002's stale timestamp or bounded unchanged-heartbeat proof still governs
role takeover without old owner or sink acknowledgements.

## Independent clocks and proposed configurable defaults

Other defaults are explicit R2 design choices, configurable only after relationship
validation; they were not specified numerically by the owner:

| Clock or allowance | Default seconds |
| --- | ---: |
| WATCHDOG inbox | 5 |
| FETCHER remote cancellation/control, only while BUSY | 5 |
| WATCHDOG heartbeat | 30 |
| Resident FETCHER heartbeat, including SLOW | 120 |
| FETCHER freshness threshold | 300 |
| Active WATCHDOG lease renewal | 20 |
| WATCHDOG stale threshold | 120 |
| Standby owner observation | 10 |
| Local process supervision, while BUSY | 0.25 |
| Transport visibility allowance | 10 |
| Bounded transport queue allowance | 30 |
| Qualified clock skew allowance | 10 |
| Publication retry/reconciliation window | 120 |

Heartbeat/freshness and lease/stale relationships must exceed the corresponding
renewal interval plus visibility, queue delay and twice the skew allowance. Slow
FETCHER command polling does not slow heartbeat/lease/inbox clocks. Fully EXITED
FETCHER has no poll, heartbeat, cancellation watcher or local supervisor: no fake
liveness continues after process exit. A co-located WATCHDOG keeps its own clocks.

ClockSet models separate deadlines, not one sleep interval for every concern.
After suspension, each overdue clock may run once and is rearmed from the current
time; missed periodic work does not cause a catch-up request burst. Faster mode
changes shorten the next due time; a transition to slower cadence may retain one
already scheduled earlier check before adopting the slow period. An idle control
or supervisor clock is disabled and re-enabled only for real outstanding work.
Production implementations instantiate/filter clocks by role and never compare
different machines' monotonic values.

## Claim, launch, execution, publication and consumption

Minimum legitimate claim TTL is:

`inbox + reachable_route + visibility + queue + 2*skew + 1 second`.

For a resident FETCHER, reachable_route is its legitimate poll interval. A faster
commissioned launcher can replace that route only with fresh qualifying evidence;
its bound includes host wake/bootstrap and is followed by the normal 20-second poll.
SSH, OS service and an external launcher are separate capabilities. No SSH does
not imply no FETCHER. A stale capability observation never shortens the promise.

Default minima are 86 seconds for normal polling and 1266 seconds for slow polling
without a faster route. The old 120-second claim TTL is therefore rejected for the
legitimate slow case. A qualified 90-second launcher yields a 176-second minimum.
EXIT with no available commissioned launcher is a valid advertised profile, but
automatic admission reports MANUAL_START_REQUIRED until actual launch/readiness;
it cannot claim it will wake itself. Clock-uncertain profiles report CLOCK_UNQUALIFIED.
These are conditional bounds for an available route, not guarantees against outages.

Execution runtime starts from actual process start and is independent of claim TTL.
Publication has its own bounded retry/reconciliation window. Exhausting it keeps
an unpublished/uncertain result retained, not reusable. Waiting for explicit result
ACK has no timer that automatically recycles an unread result. No deadline erases
an unknown side effect or rewrites the RP-010 claim/expiry CAS winner.

The effective profile exposes required intervals, idle policy, mode, next expected
FETCHER check, heartbeat/freshness, launcher kind/bound/freshness, both activity
sequences, clock confidence and minimum claim TTL. Unknown clock/exit means no
invented next check. GUI/helpers display this effective behavior, not old defaults
or an assumed fast SSH route. Later runtime queue/retry policies must actually honor
the advertised allowances; a missing bound blocks admission or explicitly exposes
an unavailable route, never silently extends a promised deadline.

## Shared provider budget

One native document implies one shared request budget, independent of its many
logical slots. The pure quota model conservatively counts independent command,
BUSY control, inbox, standby and read-before-heartbeat/lease requests. It adds a
retry multiplier and explicit read/write reserves for admission, results, ACKs,
summaries and control. Network probing itself is local network work, not a Docs
request; publishing its changes still consumes the reserve.

The 300-read/60-write per-minute values in the fixture are configurable example
ceilings, not a verified quota grant to a real account. Provider sources and quota
caveats are linked in EXCHANGE_LAYOUT_CONTRACT.md. With the draft defaults and one
standby, eight BUSY targets estimate 213.75 reads and 23.25 writes per minute,
including reserves and 1.25 retry factor. Sixty-four BUSY targets fail the same
budget despite fitting RP-009's structural storage limits. Sixty-four SLOW targets
estimate 58.25 writes per minute and fail if the configured write ceiling is 50.
The estimator never changes an owner interval to make an infeasible profile pass.

Average arithmetic is necessary but insufficient: burst windows, shared credentials,
project-wide traffic, contention/backoff, simultaneous completion, native document
size and observed latencies require RP-015/016 qualification. Admission must reserve
the worst planned BUSY population and protect control/lease/ACK headroom with an
enforced governor. Optional scans cannot consume mandatory progress capacity. Real
quotas must be read from protected setup, with honest rejection or reviewed capacity
change when obligations cannot fit. This step neither requests quota increases nor
claims a 64-target runtime benchmark.

## Acceptance and rollback limits

Fake monotonic/UTC tests cover exact thresholds, duplicate activity, restart age,
skew, suspend accounting, busy/unread holds, fully exited roles, independent clocks,
claim route budgets and capacity rejection. They do not prove actual clock/OS/network
behavior. Future scheduler, durable storage, launch, quota and GUI steps must integrate
the contract and requalify these cases. No real clocks, services, defaults, network,
credentials or workload are changed. Runtime profile rollback must occur while roles
are quiescent; it must not backdate activity, reset lease epochs or alter live deadlines.
