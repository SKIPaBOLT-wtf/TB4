# RP-011 A001 reviewed validation

Source: 6a0fea10ef65bcd97fad777532feade02ee47b5d.
Tested PR head: 396c34c4a1ffbae9a816ca827b82a797daccef7a.
PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/19 .
Contract: docs/TIMING_CONTRACT.md; profile: protocol/drafts/r2-timing-profile.json;
model: src/tb4/timing_contract.py.

## Reviewed invariants

C1: The six fixed owner values are 60/600/3600 seconds for WATCHDOG network
observation and 20/1200/1200 for FETCHER polling/inactivity. Profile parsing rejects
changes even for quota reasons. Exact threshold equality and fractional boundaries
are tested. Other default values are explicitly proposed configurable design,
not owner-prescribed or installed settings.

C2: WATCHDOG global and FETCHER target accepted-command activity clocks are separate,
even when co-located. Duplicate sequences, reads and maintenance do not refresh age;
another target's command refreshes WATCHDOG only. Validated images preserve age and
sequence through restart; missing state requires recovery. Pending/executing/
publication/unread/unknown work prevents slow/exit and never makes a lane reusable.
Age continues during that hold; the documented policy can enter idle immediately
after the hold clears if the threshold has already elapsed. Inbox, lease, heartbeat,
remote BUSY control and local supervision have distinct deadlines. SLOW retains
heartbeat; EXITED disables all FETCHER clocks while WATCHDOG continues.

C3: Claim budget includes inbox, legitimate poll or freshly qualified commissioned
launch route, visibility, bounded queue, twice skew and one-second strict margin.
Default normal/slow minima are 86/1266 seconds. The old 120-second TTL is rejected
for slow polling; a qualified 90-second launcher yields 176 seconds. No SSH does
not mean no resident FETCHER. EXIT without a fresh launcher reports manual start,
and uncertain clocks do not promise UTC admission. Runtime and publication windows
are separate; no ACK timer can recycle unread results. Average quota estimates
reserve control headroom, reject 64 BUSY targets under the example budget, and
never alter owner cadences. These are design constraints, not throughput proof.

C4: 69 timing tests cover fake monotonic/UTC thresholds, persisted activity,
cumulative skew, backward samples, clocks including/excluding suspend, bounded
catch-up, mode changes, unfinished work, missing/stale SSH/OS/external launch
routes, deadline relationships and invalid quota/profile shapes. Effective profiles
expose mode, independent heartbeat/freshness, both sequences, next check or explicit
uncertainty/manual launch. Installed v1 defaults, scheduler and services are unchanged.

## Validation

Windows Python 3.11, process-local virtualenv PATH and PYTHONUTF8=1:
python -X utf8 -m pytest tests/protocol tests/core tests/fetcher
tests/watchdog/test_scheduler.py tests/security/test_ballpark_contract.py
tests/feasibility tests/development --basetemp=<new verified work directory> -ra:
689 passed, 1 skipped in 22.24s, exit 0. Skip is the explicit POSIX SIGTERM-ignore
fixture. Exact 690 node IDs are retained. Actual shutil.which child interpreter
and tested source equality were verified before this accepted run.

Linux CI 36786346114 job 110128542397: 1150 passed, 2 skipped in 10.84s.
Progress 36786346158 job 110128542309 passed. Current post-documentation UTF-8
ledger against ownership c7279d7e0ead5f62f38492b7391631d536d31360, privacy scan,
diff and tested code equality all passed.

Desktop 36786346133 at merge build 37cfb449efc3be4fca4b34b89b303e1d48e2b12b:
Linux job 110128542738: 67 GUI tests in 2.28s; full suite 1160 passed in 17.55s.
Windows job 110128542523: 63 GUI tests, 4 POSIX-only skips in 2.88s.
WATCHDOG/FETCHER builds, bundle self-tests, GUI smoke and isolated install/uninstall
profile checks passed on both platforms. Public remote artifact receipts:
- tb4-desktop-Linux-37cfb449efc3be4fca4b34b89b303e1d48e2b12b: ID 11130520451, 312202022 bytes, sha256:ffc15a0c0e2db6043aa523e58fb7b9c7e9c0950e70898a14d89629b8bd77bdcc.
- tb4-desktop-Windows-37cfb449efc3be4fca4b34b89b303e1d48e2b12b: ID 11130216730, 119312527 bytes, sha256:58dd508be6133a7b68c159c50f446495e6971b9cd548c7408c36a43b8c25018c.

## DEF-013 and preserved failures

The first broad Windows run had 14 failures, 675 passes and 1 skip in 18.13s.
Legacy synthetic child Python execution resolved a Windows application alias
and returned 9009/Python-not-found. Timing cases passed. A scoped PATH preflight
then incorrectly compared a multi-match Get-Command result with one path and
aborted before tests. Actual shutil.which equality confirmed the intended virtualenv
is first. With that correct preflight and inherited UTF-8, the same source passed
all applicable cases. No product code or global PATH/alias setting was changed.
Initial hypothesis/failures remain in the journal. LOCAL_TESTING.md records the
qualified procedure and native exit/source checks, not a real launcher capability.

## Limits, privacy and rollback

This accepts timing semantics and synthetic models. Real OS suspend clocks, trusted
elapsed/skew calibration, atomic activity persistence, provider burst/contention
and queue guarantees, wake latency, scheduler/helper/GUI integration and live
deployment remain later gates. ClockSet is a logical model; different machines'
monotonic values are never compared. Average quota arithmetic alone cannot qualify
a topology or increase account quotas. Runtime must enforce actual reserves and
reject incompatible admission.

All data and child workloads are synthetic; build artifacts stay remote, outside
the <=100 MiB archive. No real clock, profile, credential, service, network or
installed default changed. Rollback is draft-only here. Future runtime profile
rollback requires quiescence and cannot reset epochs, age or live deadlines.
