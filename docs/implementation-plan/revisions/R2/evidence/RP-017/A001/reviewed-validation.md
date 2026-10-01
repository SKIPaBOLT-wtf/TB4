# RP-017 A001 reviewed native startup and standby
Source 0b2f89a637e95895202de5822c259e121ee6fe41; test head b775359f8b97345fa0a155957fa49d6ca0d86417; ownership base 30261fc510eb2644ff8e02d4637c11ac38652a4c; PR26.
This acceptance is for the unreleased native role composition. Existing installed v1 profiles are deliberately separate and are not claimed to implement R2 leadership. Later commissioning must provide the qualified local checkpoint/capability/clock and fixed action adapters; no deployment/migration is authorized here.

## Invariant review
C1: create_runtime_from_context dispatches an exact NativeWatchdogContext before v1 TreeHealer/registration. Native construction has no provider/action side effects. cycle checks ownership before the local scheduler, perform checks every named Action and local installation capability. Shared REPAIR/REGISTER/IDENTITY/ROUTE/RETENTION accepts only exact RecordMutation and writes through owner/revision CAS; SCAN/WOL/SSH/LAUNCH persists an UNKNOWN receipt and checks fresh ownership again immediately before one fixed external call. Trusted preparation/scheduling is pure/local, not a security sandbox for arbitrary Python.
C2: fresh incumbent keeps the fallback PAUSED/OLDER_DOG_DETECTED with no scheduler/adapter call or mutation. Repeated tick calls below standby cadence do not read again. Actual desktop worker/factory/telemetry path emits the closed reason; real GUI test checks visible paused reason and no stale PAUSED display after worker exit.
C3: distinct synthetic installation IDs and local capability/checkpoint bindings are used. Copied grants, foreign stores/capabilities and missing own grant are rejected; own persisted grant requires fresh validation/renewal. Direct stale/force takeover, ambiguous acquisition/restart INSPECT, partition/rejoin, monotonic fallback, clock loss, durable-store failure, shared readback recovery and preserved external UNKNOWN are asserted. No actual token/profile copying, credential access or host action.
C4: fallback reads leave incumbent renewals and document bytes unchanged. Every named action rejects resumed old owner before prepare/dispatch. Tests also transfer ownership during shared preparation and between durable external intent and admission. Unknown older action remains individually held while independent actions/leadership proceed. No global sink/old-host acknowledgement barrier or guarantee of revoking an already-admitted external effect.

## Reviewed limitations
50 new runtime boundary cases plus one real GUI assertion. Synthetic native SDK transport and local stores establish composition/admission behavior, not OS durability/ACL, qualified timers, provider quotas or real multi-host side effects. RP016's explicit check/dispatch suspension limitation remains. The checkpoint is bounded to one current receipt per action and one pending shared mutation; later operation engine/reconciliation owns full job identity/history and external result inspection. No implicit native production store, profile migration or second authority is installed.
Rollback stops local admission or removes the unreleased entry. It never clears another owner, lowers an epoch, replays UNKNOWN work or deletes private credential bindings.

## Observed local and CI evidence
Windows Python3.11 with process-local virtualenv PATH/PYTHONUTF8=1/PYTHONPATH=src:
python -X utf8 -m pytest tests/drive tests/watchdog tests/fetcher tests/feasibility tests/protocol tests/development tests/desktop tests/security tests/integration/test_cancellation_race_reproduction.py tests/integration/test_result_publication_reproduction.py tests/integration/test_google_transactions.py --basetemp <fresh-task-temp> -ra
1380 passed,8 skipped,4 xfailed in32.05s, exit0.1390 nodes collected in0.69s; the8 skips include two uncollected GUI modules because local PySide6 is absent, plus six POSIX-only test cases. Native CI supplies the real GUI coverage.
CI36800081941/job110172216992, merge1785beb of test head into ownership base:1572 passed,2 skipped,4 xfailed in21.17s, success.
Progress36800081919/job110172216845: all steps PASS.
The four strict expected failures remain DEF002 cancellation/deadline cases; DEF001 remains open for end-to-end publication. Local ledger16 previous VERIFIED/current test pending PASS, scanner clean and diff-check0.

Desktop36800081912 on exact merge1785beb61ed145a4521aa36222061b04de5c233f:
- Linux job110172216805: GUI68 passed in1.88s; full1583 passed,4 xfailed in16.40s.
- Windows job110172216975: GUI64 passed,4 POSIX skips in2.31s.
- Both platforms: WATCHDOG/FETCHER builds, bundle self-tests, real GUI smoke and installer/uninstaller profile-isolation checks PASS.
Provider-reported artifact checksums, not independently downloaded: Windows11135745763,119344219B,sha256:eeb382a0078c49dec1a191bf9ebf98ca3762460b0a580f3d44543cab0b7f2476; Linux11134649502,312229369B,sha256:578a3a8dfaa16c92a867a30c277f3856d18570849b30f3420b11cf5c84a4f7ed.
All native workflow steps completed successfully; no pending builds remain for this tested source.
