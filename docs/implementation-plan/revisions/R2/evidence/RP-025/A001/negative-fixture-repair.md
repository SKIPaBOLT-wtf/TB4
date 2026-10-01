# RP-025 negative fixture repair

Repair of DEF-043 under `RP-025-A001-0012`. Changed source: `40671f9e125674ae671a385e58583ef614a767e3`.

Only the new enrollment test module changed. The two-device case now creates and completes a fresh capacity-two authority through the actual Bootstrap/Commissioner adapters before discovery and owner approval. Takeover/force fixtures reuse the current verified leader enrollment map, including the exact display name. Discovery refresh uses the existing allowed ICMP method. Private staging/promotion failures use `MemoryNative.failure`; readback is armed after promotion so the intended post-commit boundary is exercised. The same durable private candidate is then recovered and read-only inspection must remain UNKNOWN with no shared mutation.

The original duplicate installation, old-owner rejection, lost-reply inspection, profile preservation and failure/no-write assertions remain. No runtime or older test source changed. Diff whitespace check passed. No test result is claimed by this source repair. All prior failed attempts, DEF-042/043 and C1-C4 holds remain.

Next: dedicated suite plus seven-file regressions on fresh task-owned bases, with exact source equality, measured exits and failure preservation.
