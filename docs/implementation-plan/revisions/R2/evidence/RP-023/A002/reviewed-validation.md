# RP-023 A002 reviewed revalidation

Exact source `a6b6dfaf728de283991ec8a34ac2c4a93d51f443`; completed actual hosted checkout `8f389e87d21f26501d7085c1f869f424525a9f51`. This review consumes [completed common qualification](../../RP-021/A002/final-combined-hosted-qualification.md), [source/assertion impact review](../../RP-021/A002/combined-source-invariant-review.md) and immutable [A001 acceptance meaning](../A001/reviewed-validation.md). It does not claim a new network scan or new build.

## C1

Scope.permits requires the exact selected interface index and approved subnet; NativeNeighbors checks current native name/index before and after bounded reads. Collection uses chosen methods and a total deadline, and failed/empty/overflow collection cannot manufacture an ONLINE/OFFLINE observation. Cache presence stays UNKNOWN; stale/future/uncertain evidence cannot refresh reachability. Discovery._current checks the current role before every trusted helper invocation.

Concrete assertions: `test_scope_requires_both_exact_interface_and_authorized_subnet`, `test_cache_is_not_current_reachability_proof`, `test_old_or_uncertain_time_cannot_refresh_catalogue`, `test_changed_interface_discards_entire_collection`, `test_empty_scope_and_disabled_method_never_call_os`, `test_total_deadline_refuses_remaining_queries`, `test_actual_loopback_identity_and_cache_read_only`, `test_actual_mismatched_loopback_identity_refuses_before_neighbor_read`.

## C2

Catalogue creates a GUID and opaque alias once in the protected image. Discovery.observe saves that image before shared publication; actual native settings restart retains it without per-device files. Shared adoption copies identity only, never trust. Hostname, address and hardware hint cannot grant enrollment; conflicting occupied identity and failed private durability preserve the previous mapping and block shared mutation.

Concrete assertions: `test_identity_alias_persist_while_hostname_is_only_a_hint`, `test_persist_before_publication_restart_stable_alias_and_minimal_projection`, `test_failed_local_persistence_never_sends_shared_write`, `test_actual_native_settings_restart_keeps_discovery_without_per_device_files`, `test_adopted_shared_identity_does_not_import_remote_trust`, `test_conflicting_shared_identity_does_not_reassign_private_mapping`.

## C3

Duplicate names remain separate untrusted identities. Reassigned addresses, lost/colliding hardware hints, conflicting verified endpoints and full catalogue/quarantine retain prior mappings or create bounded quarantine evidence. A separately verified binding can track multiple endpoints for one enrolled identity; hints cannot construct that binding. Routed IPv4/IPv6/VPN behavior is covered by explicit synthetic scope and trusted-port fixtures, not inferred from native loopback.

Concrete assertions: `test_duplicate_hostnames_are_distinct_untrusted_catalogue_entries`, `test_address_reassignment_or_lost_hardware_hint_is_quarantined`, `test_same_hardware_hint_on_another_interface_never_merges_identity`, `test_verified_peer_tracks_multiple_mutable_addresses_with_one_alias`, `test_unverified_observation_cannot_refresh_trusted_target_or_copy_its_trust`, `test_conflicting_verified_address_never_reassigns_existing_target`, `test_routed_ipv6_and_icmp_unavailable_do_not_imply_offline_or_fetcher`, `test_full_catalogue_and_quarantine_preserve_all_existing_records`.

## C4

Publication is limited to existing bounded catalogue/quarantine records and guards original artifact, enrollment, BALLPARK and FETCHER profile fields. New assignment requires related slots free; refresh retains UNKNOWN work. Exact durable plan validation rejects changed owner/authority/generation/slot/artifact. Lost replies and restart use INSPECT without resend; stale/forced takeover and takeover after private save block subsequent old-owner publication without any sink acknowledgement barrier. Public projections omit protected endpoints, names and hardware hints; no OS-name or DHCP mutation port exists.

Concrete assertions: `test_existing_identity_refresh_preserves_unknown_work`, `test_retained_work_blocks_new_identity_but_is_never_erased`, `test_lost_reply_restart_is_read_only_then_confirms_same_plan`, `test_stale_or_forced_takeover_stops_old_publication_without_all_sink_barrier`, `test_takeover_after_pending_save_blocks_cas_and_keeps_exact_inspection`, `test_restored_pending_plan_cannot_expand_scope_or_rebind`, `test_discovery_refresh_preserves_enrollment_and_effective_profile`, `test_older_local_projection_preserves_newer_shared_network_evidence`.

## Common gates and limits

Final CI: 2367 passed, 22 declared skips, four historical strict DEF-002 expected failures. Linux Desktop: 2387 passed, 17 declared skips, the same four expected failures. Windows Desktop: 2313 passed, 91 declared skips, the same four expected failures. Actual loopback tests passed on both operating systems; actual protected persistence and both WATCHDOG/FETCHER frozen self-test, GUI/setup and isolated install/uninstall checks passed. Platform-only skips were exercised on their native OS. Counts supplement the predicates above; they are not the acceptance argument.

The native held-key content fix strengthens the existing credential port without selecting a new external key. Discovery preserves the new approved FETCHER profile extension. Repository instruction profile remains UNRELEASED and activation defaults to denied. Actual Windows/Linux loopback and native protected persistence are qualified. Routed/VPN/multiple-interface topology uses explicit synthetic fixtures; real home-network collection, authenticated production peer, physical power loss and release/deployment remain later gates.

Preserve previous protected identities, aliases, bindings, quarantine and pending UNKNOWN operations. Revert only a confirmed public observation revision while stopped; never reassign a trusted target, rename an OS, reserve an address or replay a write. Only synthetic public fixtures and allowlisted test facts are exported. Original A001 source/receipts and failed hypotheses remain immutable. RP-024/RP-025 stay held until their own dependency-ready reviews.
