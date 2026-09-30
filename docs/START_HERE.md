# START HERE

TB4 is a deterministic remote-work control system with explicit logical objects,
verified transitions, bounded helpers and canonical dog/ball vocabulary.

## Current checkpoint - R2 implementation authorized, 2026-09-30

[CURRENT.yaml](implementation-plan/CURRENT.yaml) selects the active development
revision. The [R2 checklist](implementation-plan/revisions/R2/CHECKLIST.md) has
64 steps and 256 checks. Read the [work instruction](development/WORK_INSTRUCTION.md)
and [resume cursor](development/RESUME.yaml) before any action. All RP steps are
PLANNED; only planning/documentation has been authorized at this checkpoint.

The [realignment baseline](DEVELOPMENT_REALIGNMENT_PROMPT.md) records the corrected
product target and source audit. Its earlier pause before planning was fulfilled
by the owner's later request, recorded in the [R2 addendum](implementation-plan/revisions/R2/OWNER_ADDENDUM.md).
The later authorization permits implementation; a new live pilot, repair or migration
still needs its specifically documented scope.

## Minimum read order

AGENTS.md -> CURRENT.yaml -> R2 README/addendum -> WORK_INSTRUCTION.md -> active
manifest -> RESUME.yaml -> indicated step and latest attempt/defect evidence.
Load the baseline and execution contract when not already available, then only
relevant code/protocol/config. Do not load the whole repository to rediscover a
checkpoint already recorded in the cursor.

## Separate progress systems

`docs/execution-contract/` defines how development is performed (EC-01..EC-39).
Its manifest remains the only authority for those contract-point statuses.

`docs/implementation-plan/manifest.yaml` retains the historical IP-01..IP-70 plan.
Its VERIFIED entries are evidence for their recorded scope, not acceptance of R2.

`docs/implementation-plan/revisions/R2/manifest.yaml` is the sole RP status and
completed-check authority. Definitions, journal attempts, evidence and amendments
stay isolated by stable step ID. CHECKLIST and step checkboxes are projections.
RESUME is navigation; evidence, not a cursor sentence, proves completion.

## Product direction and vocabulary

WATCHDOG observes/summarizes/routes; FETCHER/RUNNER execute; deterministic helpers
own routine mechanics; the LLM states intent and consumes correlated evidence.
Use one documented WATCHDOG ingress, fixed exchange capacity and safe ownership.
Keep names such as DOG_HOUSE, BALL_PARK, KENNEL, FETCH_BALL, WAKE_BONE, DOG_SNOOZE,
DOG_SHIT, BONEYARD and DOG_POUND. Humor is allowed; ambiguity is not.

Existing operational instructions are in `docs/COACH.md` and `skill/tb4/SKILL.md`.
They describe the installed legacy contract until explicitly migrated. The planned
installed SKILL is only a public repository locator; actual compatible operating
and commissioning instructions will remain in the repository. Do not confuse
this future package design with an already delivered or installed new SKILL.

## Evidence and current implementation

Source, tests, protocol files and recorded observations establish what exists.
The active plan describes what must change. Never infer deployed completeness
from README prose, a test count, a GUI process state or a recovered single result.
The existing pilot publication/cancellation defects remain open inputs to R2.
No runtime source, installer, deployed profile or live exchange object was changed
by this planning checkpoint.
