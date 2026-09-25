# IP-15 - Configuration Relationship Validator Specification

> **Status:** Read from `../manifest.yaml`. Do not duplicate status here.

## Purpose

Define machine-checkable relationships between timing and safety settings before implementing the validator.

## Preconditions

IP-14 VERIFIED.

## Inputs / authoritative references

- `config/defaults.toml`
- `EC-20`

## Work

1. Specify minimum stale threshold relative to heartbeat and Drive visibility allowance.
2. Specify wake deadline relative to initial wait and probe interval.
3. Specify gone grace relative to heartbeat/stale detection.
4. Specify accept TTL and run-limit constraints.
5. Specify maximum retry budget and backoff sum limits.
6. Specify idle exit constraints relative to active work and heartbeat.
7. Document which invalid combinations are fatal at startup versus warnings.

## Files / modules

- `protocol/config-rules.yaml`
- `docs/CONFIGURATION.md`
- `tests/config/test_rule_spec.py`

## Required invariants

- Rules are deterministic and unit-explicit.
- A configuration that could cause premature stale/GONE classification must be rejected.

## Tests

- Canonical defaults satisfy all rules.
- Constructed inconsistent timing sets fail the expected rule.

## Failure cases

- Circular rule dependencies.
- Warning used where unsafe config should be fatal.

## Completion evidence required

- Rule specification has tests covering every defined relationship.

## Handoff state

The protocol validator can later enforce configuration consistency.

## Amendment path

`docs/implementation-plan/amendments/IP-15/`

## Evidence path

`docs/implementation-plan/evidence/IP-15/`
