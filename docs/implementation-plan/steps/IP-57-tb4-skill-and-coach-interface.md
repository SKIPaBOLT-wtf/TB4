# IP-57 - TB4 Skill and COACH Interface

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Create the minimal AI-facing control layer that teaches an agent to operate TB4 through canonical Drive objects without duplicating the full protocol in prompt text.

## Preconditions

IP-03 through IP-56 VERIFIED.

## Inputs / authoritative references

- `docs/START_HERE.md`
- `Canonical protocol specs`
- `Skill creation requirements`

## Work

1. Define COACH responsibilities: target selection, safe job construction, run-limit choice, result interpretation, next-step planning.
2. Define exact repository/Drive documents the Skill reads progressively.
3. Keep deterministic polling/retry/state mechanics in helpers rather than long prompt instructions.
4. Define how waiting work may be delegated to a watcher/sub-agent when the hosting AI supports it, with exact timing/state-change conditions.
5. Create compact SKILL.md and required agent metadata.
6. Add guidance for DONE/PARTIAL/FAILED/CANCELLED/GONE branches.
7. Validate/package the Skill using the canonical skill tooling.

## Files / modules

- `skill/TB4/`
- `docs/COACH.md`
- `tests/coach/`

## Required invariants

- Skill does not contain private root IDs or credentials.
- Skill never invents undocumented state transitions.
- Drive remains the TB4 transport; SSH is bootstrap only.

## Tests

- Skill package validation.
- Representative prompts map to correct target/state workflow.
- No giant inline SSH script generated.

## Failure cases

- Skill duplicates stale copy of full protocol instead of loading repository/Drive sources.
- Agent busy-polls instead of respecting timing guidance.

## Completion evidence required

- Packaged Skill validates and representative workflow tests/reviews pass.

## Handoff state

A fresh AI session can operate the implemented system from canonical project sources.

## Amendment path

`docs/implementation-plan/amendments/IP-57/`

## Evidence path

`docs/implementation-plan/evidence/IP-57/`
