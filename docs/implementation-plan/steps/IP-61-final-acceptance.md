# IP-61 - Final Acceptance

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Independently verify the whole project is specified, implemented, resilient, reproducible, secure, efficient, documented, and pilot-tested.

## Preconditions

IP-01 through IP-60 VERIFIED.

## Inputs / authoritative references

- `Execution contract EC-38`
- `All implementation evidence`

## Work

1. Run full unit, integration, failure-injection, security, and performance suites.
2. Run protocol validator from clean checkout.
3. Review every plan step evidence path and manifest status.
4. Verify no undocumented protocol drift between machine-readable specs, code, and docs.
5. Verify fresh bootstrap documentation and Skill package.
6. Review real pilot evidence.
7. Run public-repo privacy/secret scan.
8. Confirm no current BLOCKED/IN_PROGRESS step and repository is clean.
9. Write final acceptance report listing residual known limitations separately from completion criteria.

## Files / modules

- `docs/FINAL_ACCEPTANCE.md`
- `docs/implementation-plan/evidence/IP-61/`

## Required invariants

- This step adds no new feature.
- Any discovered functional gap reopens or amends the owning earlier step rather than being waved through.

## Tests

- Complete project test matrix.
- Clean checkout validation.
- Evidence completeness scan.

## Failure cases

- Any required prior step lacks evidence.
- Pilot or recovery criteria fail.
- Docs and implementation disagree materially.

## Completion evidence required

- Final acceptance report shows all required categories pass and references objective evidence.

## Handoff state

TB4 may be considered complete for protocol v1; subsequent work begins as a new version/plan rather than silently extending v1.

## Amendment path

`docs/implementation-plan/amendments/IP-61/`

## Evidence path

`docs/implementation-plan/evidence/IP-61/`
