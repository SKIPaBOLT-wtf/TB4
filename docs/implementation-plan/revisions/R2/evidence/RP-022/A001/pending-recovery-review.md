# Complete pending setup recovery missing at the desktop boundary

Reviewed source: f9d2a74102a462c9f8aee35a763ff257306d7118.

Source inspection: desktop.setup.open_setup constructs PrivateSettings and immediately constructs Setup. Setup starts with store.read(); read deliberately raises SETTINGS_RECOVERY_REQUIRED whenever settings.pending exists. The already qualified PrivateSettings.recover_pending verifies and promotes the same complete next-revision candidate, but open_setup never invokes it. Therefore a crash after staging a complete first identity or update leaves the normal desktop continuation blocked even when exact deterministic recovery is available. No live instance was affected or inspected.

Existing foundation/native tests already prove the read refusal and same-candidate recovery invariants. The missing integration is visible directly in this call sequence. Add actual-native regression through open_setup: inject loss immediately before promotion, inspect the complete candidate's installation ID, reopen, and assert that same ID and choices survive; partial/corrupt candidates remain untouched and blocked. Do not initialize an existing empty/ambiguous directory or replay any external operation to fix this.

DEF-029 affects RP022 C1-C4 acceptance. Existing CI runs remain historical qualification of the uncorrected source; their passing results cannot close this integration defect. Repaired source requires focused native/UI and required full platform/package revalidation.
