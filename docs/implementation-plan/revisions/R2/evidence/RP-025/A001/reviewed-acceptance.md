# RP-025 A001 first reviewed acceptance

Exact final source `a6b6dfaf728de283991ec8a34ac2c4a93d51f443`; completed actual hosted checkout `8f389e87d21f26501d7085c1f869f424525a9f51`. [Final common qualification](../../RP-021/A002/final-combined-hosted-qualification.md), [all affected source invariants](../../RP-021/A002/combined-source-invariant-review.md), [earlier source review](source-review.md) and [real helper integration qualification](helper-reference-validation.md) retain exact provenance. RP-021 through RP-024 have separate current A002 accepted receipts and immutable original A001 history. RP-025 stays in its original never-accepted A001; suspension/WIP and all failed tests remain.

## C1

FETCHER Setup has its own protected installation UUID and enrollment nonce. Explicit local owner approval selects exactly one already approved FETCHER device/slot; WATCHDOG requires a separately typed fresh VerifiedPeer proving installation, device, nonce, profile digest, current time and compatible repository pin. Boolean/raw-dict/stale/mismatched/copy-of-WATCHDOG proofs reject before persistence or CAS. Discovery, profile freshness and confirmed enrollment never grant execution; execution_authorized remains false.

Concrete assertions: `test_owner_approved_distinct_installation_changes_one_existing_catalogue`, `test_unverified_peer_or_copied_identity_never_saves_or_writes`, `test_discovery_alone_or_unselected_device_has_no_enrollment_grant`, `test_native_file_restart_keeps_both_distinct_installations_and_receipts`, `test_watchdog_only_role_still_cannot_register_fetcher`.

## C2

FetcherEnrollment.capture uses its own typed native RuntimeSnapshot, effective TimingProfile and ActivityClock rather than saved WATCHDOG/FETCHER proposals. Native process OS/architecture and running CPython are inspected; other PATH interpreters remain UNQUALIFIED and are never executed. A frozen application is not asserted to be external Python. Reports retain disabled capability states, actual cadence/idle/hold modes, next check, revision and conservative stale/future/unknown-clock freshness in the bounded codec.

Concrete assertions: `test_actual_runtime_policy_not_saved_watchdog_or_fetcher_proposal_drives_report`, `test_profile_revision_and_freshness_are_effective_not_a_ready_guess`, `test_native_process_os_python_and_unqualified_path_presence_have_no_private_output`, `test_frozen_app_is_not_an_external_python_interpreter`, `test_effective_owner_cadence_clock_and_hold_modes_roundtrip`, `test_future_stale_boundary_and_unknown_clock_never_become_fresh`, `test_compact_profile_rejects_ambiguous_encoding`.

## C3

Same confirmed report is read-only idempotent; reinstallation cannot take a prior identity. Duplicate installation, changed device/alias/capacity, stale/gapped/future profile and malformed durable owner/authority/pin/after-image refuse without remapping or truncation. Exact protected operation is saved before CAS; failed private save or peer/owner change leaves the same inspection-only plan. Lost reply, cancellation, restart and immediate takeover never resend it. Revocation preserves unrelated UNKNOWN work and generations; complete 64-slot profiles fit the existing budgets.

Concrete assertions: `test_same_confirmed_report_is_idempotent_but_reinstall_cannot_take_its_identity`, `test_conflicting_or_stale_report_preserves_confirmed_state`, `test_same_installation_cannot_enroll_second_approved_device_or_rebind_local_choices`, `test_lost_reply_restart_only_inspects_exact_operation_after_takeover`, `test_unsent_durable_intent_cancelled_restart_remains_unknown_without_resend`, `test_persisted_pending_tamper_is_rejected_before_recovery`, `test_peer_change_after_durable_intent_is_inspection_only`, `test_whole_record_headroom_rejection_does_not_reset_or_truncate`, `test_all64_preallocated_targets_keep_complete_profiles_within_existing_budgets`, `test_revocation_preserves_unknown_work_history_and_prevents_old_binding`.

## C4

Bounded summary filters eligible FETCHER roles before pagination and refuses a hidden bound FETCHER on an unapproved role. It reports the actual profile, disabled capabilities and conservative freshness/liveness, always with execution_authorized false. Credential availability comes only from this WATCHDOG installation's current purpose/target/trust-bound resolver; foreign resolver, revoked key and copied binding cannot imply availability. Public views omit handles, paths, trust material and installation UUID. Mixed WATCHDOG/FETCHER/combined/all-WATCHDOG summaries and discovery refresh preserve legitimate profiles.

Concrete assertions: `test_summary_pages_only_initially_approved_fetcher_roles`, `test_summary_cannot_hide_bound_fetcher_on_unapproved_role`, `test_native_own_credentials_availability_is_not_copied_or_exposed`, `test_discovery_refresh_preserves_enrollment_and_effective_profile`, `test_profile_revision_and_freshness_are_effective_not_a_ready_guess`.

## Common gates, repairs and limits

Both OS Desktop jobs passed all 79 dedicated enrollment/profile cases. Complete exact-source CI: 2367 passed/22 declared skips/four historical strict DEF-002 expected failures; Linux Desktop: 2387/17/four; Windows Desktop: 2313/91/four. Native protected persistence and credential availability, Qt/setup, actual loopback and all 75 BALLPARK cases passed on each applicable OS. Both WATCHDOG and FETCHER frozen self-test, GUI/setup and isolated install/uninstall profile checks passed on Windows and Linux. Provider artifact digests were read back; large bundles were not downloaded, deployed or independently rehashed.

The actual original held-key mutation assertion remains unchanged; new current-content and scratch-wipe native negatives qualify DEF-046. The exact-public-reference checkpoint helper and complete current/main-history checks qualify the administrative integration; all original history/concurrency/source-existence guards remain. Supplemental CURRENT-selected semantic gate tests retain all original other assertions and historical RP-012 meaning. Each named regression is reviewed; counts alone do not accept the step.

Production authenticated peer/transport and integrated setup/runtime deployment are later gates. Actual instruction profile remains UNRELEASED/default-deny and execution_authorized is always false. No physical power-loss, real home topology or field ARM64 qualification is inferred. Revoke only an explicitly confirmed FETCHER enrollment with preserved slot generation and history. Keep previous identity/profile, unrelated artifacts/BALLPARK and exact UNKNOWN private plans; no copying WATCHDOG credentials or destructive reset/resend. Public documentation uses synthetic fixture facts only. This review gives no live network/deployment/release or uncertain-effect replay permission. DEF-042 through DEF-048 remain OPEN until a separate coherent resolution record proves every required recheck accepted.
