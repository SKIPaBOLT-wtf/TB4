# RP-020 amendment A001: immutable journal action capitalization

The original RP020 action IDs were published in lowercase and failed the existing
uppercase schema. This development-metadata amendment adds only an explicit,
closed append-only action_case_correction read view. Original records remain
byte-for-byte immutable. Only a prior same-item/attempt action group can map to
its exact uppercase ASCII name, with original INTENT source, scope and check.
Collision, rename, extra fields, mixed/repeated correction and new malformed
records fail. Ordinary action chronology and actual PASS/FAIL/UNKNOWN facts
remain authoritative. There is no protocol, owner permission or acceptance
criterion change. See DEF-025 and WORK_INSTRUCTION for validation obligations.
