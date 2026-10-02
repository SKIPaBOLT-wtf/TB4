# RP-025/A001 — new public-reference test line-ending mismatch

Source `276ce3a035b66c08cab20976dde911cfc3e5f506`; INTENT `RP-025-A001-0066`; session20661. Targeted suite: **28 passed,1 failed**, no skips,11.38s; exit1. Full development and actual repository/prospective gates were not started.

The positive new fixture prepares/revalidates successfully, then compares a Windows local CRLF journal to a LF plan prefix. Exact read-only inspection of the same task-owned synthetic fixture: local CRLF=true, committed public Git blob CRLF=false, normalized local equals public Git blob=true. The fixture's disk bytes differ from its authoritative published representation. This failure does not prove any rewrite of public Git history.

Correction must check the **exact committed Git blob prefix**, without normalization, and separately retain the existing unchanged local byte assertion after publication/readback. This strengthens the actual public-history proof and leaves source/ledger/runtime implementation and original assertions unchanged. Retain failed attempt; complete targeted/full development/current/history/scanner and actual prepare/validate_plan graph qualification under a fresh INTENT before acceptance.
