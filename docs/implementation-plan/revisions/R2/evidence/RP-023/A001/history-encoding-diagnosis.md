# Local history decoding diagnosis

INTENT0045 read-only diagnostic exited0. Local Python reported cp1252 and UTF8_MODE0. First mismatch: `docs/implementation-plan/revisions/R2/evidence/RP-008/A001/storage-decision.md`.

- Raw base91d701 Git bytes decoded explicitly as UTF-8 equal the working UTF-8 file (checkout CRLF normalized for comparison):true.
- Raw base blob equals current HEAD blob:true.
- Default subprocess-decoded view equals explicit UTF-8 view:false.

No historical file differs. The local validation invocation omitted PYTHONUTF8=1, which the hosted Windows workflow already declares. This establishes an environment precondition failure, not history mutation or failure of the runtime source. The accepted historical bytes must remain untouched. Future Windows development validation in this task uses process-local PYTHONUTF8=1 and a fresh task-specific pytest basetemp; this changes neither system settings nor ACLs. Remaining final review must revalidate the entire history in that qualified environment, not suppress the immutable-evidence check.
