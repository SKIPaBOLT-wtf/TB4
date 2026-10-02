# Initial targeted Windows qualification - FAIL

Source: f638b9ec28091554f879dd59cd4b8db3105f1251. Actual checkout: 15e18de3cd4c9d8e2ca448b29c6c0e3af86a0f89. Local exec session 11317.
Procedure: pytest on the 15 declared target suites, including network schema/store/helper/native/Qt and discovery/BALLPARK/enrollment/first-run/settings/instruction/installer regression tests. Exit 1; 346 collected cases, 333 passed, 3 failed, 10 Linux/POSIX-specific skips; duration 26.000 s (JUnit 25.582 s). No xfail or collection error. The skill/current/history/scanner/diff gates were not run after the failed target gate. No test/step accepted.

Failed cases:
- tests.drive.test_network_table_schema.test_fresh_verified_addressing_is_scoped_to_only_that_action_and_endpoint
- tests.drive.test_network_table_schema.test_stale_unknown_platform_and_noncomputer_descriptions_are_distinct
- tests.security.test_network_table_native.test_native_table_lock_blocks_competing_writer_without_losing_revision

Observed facts: after an unverified neighbor hint at another synthetic address, the address prerequisite stayed SATISFIED for the unchanged previously known endpoint. The router-description test remained INADEQUATE_DESCRIPTION after changing only its kind; the existing FETCHER role/platform choices were retained. The native lock case raised closed native SETTINGS_BUSY during proposal preparation inside the locked region, before its approve call. Source review shows that the new table binding accessor does not normalize native store errors to its module's NetworkTableError API. Initial hypotheses: test stimuli may be assuming identity movement/clearing retained roles; lock stimulus may occur before the intended mutator. These are not claims that previously accepted discovery/native locking is wrong.

DEF-049 tracks new qualification stimulus/expectation errors; DEF-050 tracks the new module's native binding diagnostic API. Origins remain unproved until isolated diagnosis/recheck. Hold unaccepted RP-026 C1-C4; accepted predecessors remain unchanged. Raw logs/JUnit are retained only locally, not published because fixture paths/native identifiers are private. All public fixture values are synthetic. No actual network/assignment/provider request or user settings changed.

Next: published diagnostic/repair INTENT; establish identity-drift stimulus through a fresh trusted binding, explicitly remove roles for the non-computer scenario, prepare the lock proposal before locking and normalize native binding error. Preserve every old failure and assert the same endpoint/freshness/adequacy/lock invariants; repeat target qualification only after its repair outcome.
