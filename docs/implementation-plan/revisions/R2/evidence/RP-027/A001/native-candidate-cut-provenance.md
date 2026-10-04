# RP-027.C2 same failed native cut provenance

Source: `c323da611eb98de3966145e226679335976b3f22`; same original run checkout: `43539cb4712e10d48d089a51b91f137d2f727b77`. Only those three failed native fixture roots were read, after resolved task-root containment checks. Actual protected PrivateSettings/native codecs and Setup validation verified existing frames; no promotion, test/source edit or provider call occurred during this inspection.

{
  "source": "c323da611eb98de3966145e226679335976b3f22",
  "run_checkout": "43539cb4712e10d48d089a51b91f137d2f727b77",
  "failed_cases": 3,
  "read_only": true,
  "facts": [
    {
      "store": "archive",
      "one_complete_pending_frame": true,
      "revision": 1,
      "previous_none": true,
      "current_absent": true,
      "native_protection_binding_and_digest_verified": true,
      "phase": "STAGING",
      "original_profile_matches_recorded_base": true,
      "original_known_operations": 2,
      "original_unknown_operations": 0,
      "exact_seed_or_archive_matches": true,
      "frame_promoted": false,
      "provider_invoked": false
    },
    {
      "store": "profile",
      "one_complete_pending_frame": true,
      "revision": 1,
      "previous_none": true,
      "current_absent": true,
      "native_protection_binding_and_digest_verified": true,
      "phase": "STAGING",
      "original_profile_matches_recorded_base": true,
      "original_known_operations": 2,
      "original_unknown_operations": 0,
      "exact_seed_or_archive_matches": true,
      "frame_promoted": false,
      "provider_invoked": false
    },
    {
      "store": "transaction",
      "one_complete_pending_frame": true,
      "revision": 1,
      "previous_none": true,
      "current_absent": true,
      "native_protection_binding_and_digest_verified": true,
      "phase": "STAGING",
      "original_profile_matches_recorded_base": true,
      "original_known_operations": 2,
      "original_unknown_operations": 0,
      "exact_seed_or_archive_matches": true,
      "frame_promoted": false,
      "provider_invoked": false
    }
  ]
}

Each actual interruption retained exactly one first-revision complete native pending frame, with no current frame at its selected store. Metadata phase is STAGING. Original profile/revision/hash, native directory binding/frame digest, exact staged seed or full immutable archive and two known operation outcomes match. Actual physical paths, native principals/directory IDs, installation IDs, hashes, configuration and credential metadata are omitted from this evidence.

The source's accepted Windows/Linux native locked wrappers preserve SettingsError and translate other exceptions to SETTINGS_STORE_UNAVAILABLE. The injected OSError reaches that wrapper, whereas the new test assumed COMMIT_UNCONFIRMED. This establishes DEF-060's fixture expectation mismatch. It does not substitute for the remaining post-cut recovery assertions, which must run unchanged after the one-file repair. No original history/workload or application protection is changed.
