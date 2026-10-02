# RP-027 A001 initial-coverage fixture provenance

Diagnostic INTENT RP-027-A001-0025 verified at894be780162b508b77697c6ba4b25286b7cb4362. Source ac587b6b6856e3c7785030720ee9c120c2fad0e5; same completed run checkoutfe675ccabbe2b4365efd877d1c3959295032641c. Read-only; no provider operation, new test, source edit or fixture mutation.

Same owned failed native frames, allowlisted facts:

- all-native-maintenance: grant epoch2, receipts0, election pending=false, mutation pending=false, maintenance reserved=true, initial epoch condition=false.
- all-action-capacity: grant epoch2, receipts9, election pending=false, mutation pending=false, maintenance reserved=true, initial epoch condition=false.

Actual factory trace: test_ballpark_publication.ready → test_discovery_workflow.build → test_first_run_storage.prepared creates the original ACTORS[0] bootstrap/commissioning at epoch1, then build creates a new Setup and explicitly acquires at stale clock220, yielding epoch2. New guarded_system reused that accepted later-owner fixture. Its initial-coverage guard correctly refuses. The native pending-frame absence follows that prior refusal before effect intent staging; no interrupted provider call is inferred. Existing native checkpoint protection refusal is NATIVE_CHECKPOINT_INSPECT_REQUIRED and its negative test expected an unrelated broader code.

Actual Bootstrap.initial_grant validates the same seeded owner/acquisition/authority freshly, with no election rewind. Correct repair: construct a new test-only initial Setup with a controlled synthetic bootstrap identity before its first native write, run the existing real Bootstrap/NativeCommissioning/Commissioner/discovery/descriptor adapters once, and obtain the verified original initial grant. The previous failed fixture remains unchanged. Use this truthfully initial factory only for new guard tests; retain later-owner refusal and every failed predicate. Change the native negative regex to the observed precise closed code, retaining no-success/no-mutation assertions.

DEF-058 origin is now proven in the new fixture composition/expectation, not accepted predecessors. Original hypothesis remains UNTESTED and a separate supported fact is appended. No C1-C4 acceptance. Next: verified two-file fixture/support repair INTENT, source preservation/outcome, then fresh exact24-target repeat plus a real-bootstrap initial-grant regression.
