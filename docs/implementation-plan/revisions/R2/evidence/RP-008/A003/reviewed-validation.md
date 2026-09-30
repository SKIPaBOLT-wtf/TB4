# RP-008 A003 reviewed owner-directed design

Design source: `bf148dd888824e32dc58958bc96e7b5f03b6b252`. Tested head: `6090d2522a6156123a7a1f1e89c4bd501884dbb5`.
PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/16 .
Authority: owner's explicit correction recorded in RP-008-A002-0013;
current contract: `docs/implementation-plan/revisions/R2/amendments/RP-008/A-002-available-owner-takeover.md`.
The earlier all-sink activation barrier is superseded. A001/A002 evidence remains immutable history.

## Check-by-check review

- C1: Retain A001's verified raw Drive precheck/write counterexample and isolated real Docs strict required-revision success/stale rejection/fresh success/deleted-fixture result. One fixed Docs authority supports the selected shared ownership CAS. Native Docs ACLs are not field-level TB4 authorization; enrolled trusted clients must validate role rules. No alternate shared-folder adapter is assumed qualified.
- C2: 28 new `test_available_takeover.py` cases directly exercise the corrected policy: powered-off old owner plus UNKNOWN work activates a new owner immediately, with no sink/old-host response path; all six contender orders yield one successful stale-snapshot CAS; fresh renewal rejects stale contenders; an already expired first read claims immediately. Force flags, lost requests, expiry, old epochs, names shared by distinct instances, partitions and observation clock faults have explicit negative assertions.
- C3: Commissioning remains owner-authorized and tied to exact domain/authority identity. Valid incumbent wins unless stale or an explicit force request is issued. One increasing epoch plus exact revision fences shared writes. New authority requires no all-sink drain. Unknown old operation records persist separately and cannot justify replay or blocking unrelated WATCHDOG duties.
- C4: Select owner-approved **immediate stale-record or requested CAS takeover**, visible owner computer name and correlated GUI forced request. Atomic shared control mutations reject old snapshots and old identities even after a fresh read. Each actor checks role/request before new dispatch; an already admitted external action can overlap role takeover. This limitation is demonstrated by a counterexample, not hidden behind an unproven zero-overlap assertion. EC-16, R07 and planned RP-016/RP-053 acceptance changes are explicit amendments.

A GUI force request first publishes the requester/expected epoch/expiry, stopping old-owner shared writes; its requester then claims a new epoch without any acknowledgement. Concurrent flags cannot overwrite each other. A dead requester has bounded expiry, and ordinary stale-role acquisition can still win. The UI's actual implementation remains RP-053; no installed button or runtime takeover is claimed here.

## Exact validation

Windows Python 3.11: `python -X utf8 -m pytest tests/feasibility tests/drive tests/development tests/coach/test_instruction_selection.py --basetemp=<new verified workspace directory> -ra`: **326 passed, 1 skipped**, 14.37 s; child exit 0. The skip is POSIX mode-bit checking; Windows secret-store ACL qualification remains RP-020.

Linux CI [36778251106](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36778251106), job 110101515781, passed the full suite. Progress [36778250863](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36778250863), job 110101515970, passed development tests, ledger, history and scanner. Exact Linux count/duration are in the matching journal outcome after log inspection.

Local `python -X utf8 -m tools.development.ledger --base b41faf1540d7fbbb8b173a0d284bf0563a68a578`, public scan and diff checks all returned 0. Diff of historical A001/A002 evidence from A003 ownership `8856fd00741e20b8fe94778c2cb70ad63ba21be9` is empty. Exact 327 collected test IDs are in `collected-tests.txt`.

A001 raw-provider/model cases and A002 historical global-barrier cases remain regression/comparison tests; only the 28 A003 cases define the new takeover semantics. Test counts alone do not accept a design. No production/protocol/packaging change requires a Desktop build.

## Limits, failure history and rollback

A002 documents failed temporary cleanup, wrong module invocation, the corrected immutable-evidence banner (DEF-011), and verified Windows UTF-8 invocation requirements. They are not deleted or reinterpreted as initial success. Use a new isolated basetemp and `-X utf8` for local ledger/checkpoint work. DEF-010's earlier POSIX test repair passes this regression scope.

These are design/model results, not an actual Docs adapter, GUI or multi-host installation. Later RP-015/016 must qualify actual conditional writes and shared ownership; RP-011 timing; RP-053 UI; RP-058/060/063 real failure scenarios. An unreachable shared authority still prevents shared writes; an unreachable former WATCHDOG or sink does not block takeover when authority is available. Already dispatched external effects can overlap: exact busy/UNKNOWN operations retain separate constraints and must never be blindly replayed.

Synthetic names only; real computer names stay in protected deployment records/private GUI. No actual root, profile, credential, network, service or installed application was changed. Preserve one domain, fixed identity, increasing epochs and unread/uncertain results; do not restore a stale snapshot or mix v1 raw control with the new authority. Live migration still requires separate authorization.