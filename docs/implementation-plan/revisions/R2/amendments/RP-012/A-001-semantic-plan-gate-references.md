# RP-012 A-001 — supplemental semantic gate-reference validation

2026-10-02. DEF-048, detected by final RP-021–025 held common qualification,
exposes an original RP-012 validation-harness assumption at
d31bfe687bda0944307ca82f279d2a2296c4bacc. The original identity test searched
inline YAML text. Valid block serialization falsely fails it, while a comment
can falsely stand in for a deleted gate step.

The invariant remains unchanged: the exported security matrix must match policy,
every nonempty gate must reference a real current-plan step and its canonical
definition. Use the selected CURRENT manifest and existing duplicate-safe
loader, independent of block/inline/JSON serialization. Test every missing gate
masked as comment text, mismatched definitions and duplicate keys. Policy,
GATES, protocol export, runtime/native assertions and authorization are unchanged.

Original RP-012/A001 accepted source, journal and receipts stay immutable. Exact
current identities/export remain valid; equivalent formatting does not invalidate
that semantic runtime invariant. This supplements validation coverage and does
not claim the old source passed newly added negatives. Current repair/evidence
belongs to already-open RP-021/A002 common qualification, with responsible-step
provenance explicitly linked here and in DEF-048. All RP-021–025 holds and the
existing DEF-046 transitive rechecks remain until required final source/platform
qualification and per-invariant review pass. No acceptance/guard exception or
new deployment authority is created.
