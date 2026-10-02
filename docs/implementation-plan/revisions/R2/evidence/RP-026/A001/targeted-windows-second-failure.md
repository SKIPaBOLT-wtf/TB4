# Repaired Windows target qualification - second failed run

Source: f719927c8eed0df2d98842f9782ff4b3068f22f4
Exact test checkout: b052a3abbca0825f448f960bfa3d919c9b11560b
INTENT: RP-026-A001-0021; STARTED: RP-026-A001-0022; local-exec-session-84478.
Run: rp26-targeted-002, native Windows CPython 3.11.9, offscreen Qt, isolated synthetic fixtures.

The declared 15-suite pytest gate exited 1 in 29.485 seconds (JUnit 29.020 seconds): 356 collected, 337 passed, one failed, 18 Windows/POSIX-specific skips, no errors or expected failures. The group stopped at this gate; skill/current/history/scanner/diff gates did not execute. The outer shell wrapper returned zero after output cleanup; acceptance uses the captured pytest exit 1 and JUnit, never the shell-cleanup exit.

Failed invariant stimulus:

tests.drive.test_network_table_schema.test_fresh_verified_addressing_is_scoped_to_only_that_action_and_endpoint

The explicit trusted FIXED_HELPER observation was rejected as OUT_OF_SCOPE where the new stimulus expected OBSERVED. The unverified-hint quarantine and earlier stable-address freshness assertions passed first. Cause is still unproven; inspect the approved-scope requirement before changing any predecessor policy. Original final endpoint-bound STABLE_ADDRESS_REQUIRED assertion remains.

The other initial role-retention and native-lock/error scenarios passed on this exact source. This does not close DEF-049/050 or accept RP-026; all C1-C4 revalidation holds remain. Preserve both failed runs and their source refs. No live table, network, router, credentials, installed skill or accepted predecessor was changed.

Task-only input patch preparation initially rejected multiple patch operations targeting the same existing input path; no test had launched. It was corrected before creating this fresh run. A follow-up poll of an already-completed session returned unknown-process; the existing structured result/JUnit established completion, so no run was repeated.

Next: publish a bounded diagnosis/repair INTENT for the new FIXED_HELPER scope stimulus, then a new fresh exact-source qualification INTENT. Raw fixtures/logs/JUnit remain local; this sanitized receipt contains no private host/path/topology/native binding values.
