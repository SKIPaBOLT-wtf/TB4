# RP-025/A001 — real reopening preparation reference failure

Source `6162dea493900e64b916ced098889d75849dc43f`. The pure RP-021/A002 repair candidate was constructed, but `checkpoint.prepare` ended exit 1 at staged `_journals` → `public_path`: `REFERENCE_MISSING`. No new-attempt candidate was published and no native or accepted state changed.

The staging helper copies docs only. Actual historical journals preserve original source evidence (including source_evidence_correction targets), whose files exist in the real public checkout and are checked by the ledger. A docs-only prospective tree cannot satisfy their existence checks. The real-root current/history gates passed before this preparation. The original default safety checks remain valid; no check will be suppressed.

DEF-047 tracks complete source-reference staging integration under unaccepted RP-025. The authorized manual checkpoint path will stage docs plus only exact referenced public tracked regular files and invoke the same schema, current ledger, transitions, defect/history, append-only and publication readback gates. This allows the native repair without weakening provenance. Fix and qualify actual prepare/validate_plan integration before final RP-025 acceptance; keep all its holds meanwhile. No originating historical source is asserted without further evidence.
