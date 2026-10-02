# RP-024 A002 reviewed revalidation

Exact source `a6b6dfaf728de283991ec8a34ac2c4a93d51f443`; completed actual hosted checkout `8f389e87d21f26501d7085c1f869f424525a9f51`. Read [final common qualification](../../RP-021/A002/final-combined-hosted-qualification.md), [source invariant review](../../RP-021/A002/combined-source-invariant-review.md) and original [A001 review](../A001/reviewed-validation.md). No live publication or new build occurred in this review.

## C1

GuidedBallpark fetches an eligible repository closure and pins its immutable commit, hashes, runtime and policy. Restart verifies the original catalogue/closure, even when main advances. Closed proposals contain approved opaque identities and enumerated nonsecret choices only; a proposal never equals owner approval. Missing, unreleased, revoked or changed guidance refuses and preserves the private draft. No device text or secret selector enters questions or instructions.

Concrete assertions: `test_partial_choices_restart_request_only_missing_and_never_expose_hints`, `test_untrusted_proposal_cannot_inject_private_data_instructions_or_authority`, `test_proposal_is_never_owner_approval`, `test_restart_keeps_original_pin_when_main_advances_and_rejects_changed_bytes`, `test_unreleased_or_missing_guidance_has_no_fallback`, `test_restored_pin_must_match_original_repository_catalogue`.

## C2

Exact current owner and fresh instruction boundary guard one RecordMutation CAS to preallocated objects. The protected owner decision, selected identities, authority marker, previous revision, complete record budgets and provenance are validated before durable save, then owner/release are checked again before START. Artifact, discovery, enrollment, FETCHER profile and UNKNOWN work fields are preserved or incompatible changes refuse. The prior local descriptor becomes active only after exact remote confirmation; lost reply, cancellation, revocation and takeover recover by read-only inspection without another write.

Concrete assertions: `test_atomic_minimal_revision_preserves_artifacts_discovery_and_unknown_work`, `test_lost_reply_keeps_old_active_then_restart_only_inspects_exact_revision`, `test_new_owner_or_force_request_blocks_old_owner_without_sink_ack_barrier`, `test_revocation_after_pending_save_leaves_read_only_unknown_without_writing`, `test_takeover_between_local_intent_and_write_keeps_pending_inspection`, `test_newer_remote_revision_does_not_confirm_or_overwrite_lost_old_write`, `test_all_64_slots_roundtrip_with_maximum_catalogue_fields_within_fixed_budgets`.

## C3

LLM setup questions and descriptor views expose only opaque identity/alias, closed role/platform/transport selections, effective timing, revision and explicit staged/active/unknown status. They omit endpoints, interface names, hardware hints, installation credential bindings and material. Choices are not qualification or execution grants. Actual Qt separates approving the draft from publishing it and offers only inspection after an uncertain publication; provider text is rendered as closed plain status.

Concrete assertions: `test_exact_owner_decision_stages_private_descriptor_without_any_shared_write`, `test_partial_choices_restart_request_only_missing_and_never_expose_hints`, `test_untrusted_proposal_cannot_inject_private_data_instructions_or_authority`, `test_real_qt_owner_review_approval_is_separate_from_publication`, `test_real_qt_restart_unknown_exposes_only_inspection`.

## C4

Blank deployment has no machine seed or implicit scan. Partial choices remain durable and request only missing fields. Wrong root/domain/schema/authority, malicious extra fields, stale discovery decisions, cancelled setup, altered pin or pending plan, overflow and failed native private saves refuse without replacing the prior descriptor. Codec rejects bool/unknown values and the full 64-slot bounded layout round-trips. Default repository guidance remains UNRELEASED with no released build.

Concrete assertions: `test_blank_deployment_has_no_machine_seed_or_implicit_scan`, `test_invalid_closed_selection_preserves_draft`, `test_discovery_change_requires_new_proposal_before_confirmation`, `test_protected_frame_rejects_wrong_binding_or_tampered_draft`, `test_local_pending_save_failure_never_reaches_shared_write`, `test_invalid_remote_binding_never_writes_or_activates`, `test_remote_record_over_budget_cannot_be_replaced_or_reset`, `test_compact_codec_rejects_ambiguous_or_unrecognized_values`, `test_repository_profile_remains_unreleased_and_hashes_include_setup_guidance`.

## Common gates and limits

Both Desktop jobs passed all 75 BALLPARK tests with actual Qt owner controls and native protected restart. Final full CI 2367 passed/22 skips, Linux Desktop 2387 passed/17 skips and Windows Desktop 2313 passed/91 skips; each retains four historical strict DEF-002 expected failures. Native, protected credentials, loopback, 79 FETCHER enrollment/profile tests and both-role frozen core/GUI/setup/install/uninstall checks passed. Platform-only skips have their native OS evidence. Concrete invariants above supplement these counts.

No live-domain publication, authenticated production adapter/peer, released build, integrated end-to-end setup deployment or physical power-loss test is claimed. Guidance/profile remains UNRELEASED/default-deny; synthetic trusted ports prove bounded component composition only. No release, operational migration or new transport authority is inferred. Keep the prior confirmed descriptor active until the exact new revision is confirmed. Preserve protected choices, original instruction pin, identities, profiles, external credentials and pending UNKNOWN plans; cancellation or rollback cannot erase owner decisions or replay a publication. Public exports contain only synthetic fixture facts. Prior A001 acceptance and every failed hypothesis remain; RP-025 must receive its own first acceptance after this dependency is confirmed.
