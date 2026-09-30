# Development record templates

Templates are field contracts and examples, not actual completed work. Replace
placeholder values from verified observations; never copy a fabricated timestamp,
source SHA, result or deployment identifier. RP-001/RP-002 will automate validation
and publication. Until then the same pre-action and post-action rule is manual.

Use EVENT.json for each journal event, ATTEMPT.md for a bounded attempt summary,
EVIDENCE.md for a per-check acceptance receipt, DEFECT.yaml for investigation
linkage and RESUME.yaml for the cold-start cursor. A journal may contain many
phases inside one attempt. Append events; do not edit an earlier failed hypothesis
out of history. Use a correction event with related_event.

For a clerical STARTED-to-INTENT mislink only, the optional typed
`reference_correction` contains `field: related_event`, the exact `old_value`
and the earlier INTENT `new_value`. The CORRECTION's `related_event` names the
original STARTED. Match its action/check/source/run identity; use RECORDED with
observed justification. It never changes outcome/authorization or settles work.
See R2 amendments/RP-010/A-001-started-reference-correction.md. Ordinary prose
corrections require no such object; original records always remain unchanged.

Public records contain only safe metadata/procedures and synthetic fixture names.
A public evidence locator must not be a real private Drive object ID, key path or
unreviewed log download. Private evidence can be represented by a non-resolving
opaque local reference in protected records, not uploaded to GitHub.
