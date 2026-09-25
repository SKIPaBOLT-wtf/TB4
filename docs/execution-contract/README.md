# TB4 Execution Contract

This directory stores the **development contract** for TB4. It is deliberately separate from `docs/IMPLEMENTATION_PLAN.md`.

- Contract points define **how the project is developed**.
- Implementation-plan steps define **what concrete engineering work is done next**.
- The only authoritative status for contract points is [manifest.yaml](manifest.yaml).
- Never duplicate a point's authoritative status inside its point file.

## Status lifecycle

```text
ACTIVE -> IN_PROGRESS -> VERIFIED
   |          |
   |          +-> BLOCKED
   |
   +-> SUPERSEDED   (only through an explicit amendment)
```

`VERIFIED` requires evidence. A point must not be marked VERIFIED only because someone believes it is satisfied.

## Change isolation

For point `EC-XX`:

- Canonical rule: `points/EC-XX-*.md`
- Amendments: `amendments/EC-XX/`
- Verification evidence: `evidence/EC-XX/`

This prevents one point's completion material from becoming mixed with another point.

## Canonical points

- [EC-01 — Purpose of This Prompt](points/EC-01-purpose-of-this-prompt.md)
- [EC-02 — Privacy Boundary](points/EC-02-privacy-boundary.md)
- [EC-03 — Repository Is Project Memory](points/EC-03-repository-is-project-memory.md)
- [EC-04 — Required Project Entrypoints](points/EC-04-required-project-entrypoints.md)
- [EC-05 — Public Implementation Plan](points/EC-05-public-implementation-plan.md)
- [EC-06 — Step Size Rule](points/EC-06-step-size-rule.md)
- [EC-07 — Required Format for Every Plan Step](points/EC-07-required-format-for-every-plan-step.md)
- [EC-08 — One Step at a Time](points/EC-08-one-step-at-a-time.md)
- [EC-09 — Protocol Vocabulary Is Canonical](points/EC-09-protocol-vocabulary-is-canonical.md)
- [EC-10 — Active State and History Stay Separate](points/EC-10-active-state-and-history-stay-separate.md)
- [EC-11 — Deterministic Control Path](points/EC-11-deterministic-control-path.md)
- [EC-12 — State Mutation Contract](points/EC-12-state-mutation-contract.md)
- [EC-13 — Ambiguous Write Rule](points/EC-13-ambiguous-write-rule.md)
- [EC-14 — Helper-First Architecture](points/EC-14-helper-first-architecture.md)
- [EC-15 — Component Ownership](points/EC-15-component-ownership.md)
- [EC-16 — Concurrency and Fencing](points/EC-16-concurrency-and-fencing.md)
- [EC-17 — Script and Payload Execution](points/EC-17-script-and-payload-execution.md)
- [EC-18 — Result Size](points/EC-18-result-size.md)
- [EC-19 — Configuration Classes](points/EC-19-configuration-classes.md)
- [EC-20 — Configuration Relationships](points/EC-20-configuration-relationships.md)
- [EC-21 — Efficiency](points/EC-21-efficiency.md)
- [EC-22 — Failure Scopes](points/EC-22-failure-scopes.md)
- [EC-23 — Partial Execution](points/EC-23-partial-execution.md)
- [EC-24 — Recovery Philosophy](points/EC-24-recovery-philosophy.md)
- [EC-25 — Tree Repair](points/EC-25-tree-repair.md)
- [EC-26 — Test-First Dependency Order](points/EC-26-test-first-dependency-order.md)
- [EC-27 — Testing Rule](points/EC-27-testing-rule.md)
- [EC-28 — Failure Injection](points/EC-28-failure-injection.md)
- [EC-29 — Machine-Readable Specification](points/EC-29-machine-readable-specification.md)
- [EC-30 — Protocol Changes](points/EC-30-protocol-changes.md)
- [EC-31 — Git Discipline](points/EC-31-git-discipline.md)
- [EC-32 — Step Completion Loop](points/EC-32-step-completion-loop.md)
- [EC-33 — Completion Evidence](points/EC-33-completion-evidence.md)
- [EC-34 — Decision Records](points/EC-34-decision-records.md)
- [EC-35 — Step-Planning Algorithm](points/EC-35-step-planning-algorithm.md)
- [EC-36 — Plan Review Before Execution](points/EC-36-plan-review-before-execution.md)
- [EC-37 — Initial User-Provided Step](points/EC-37-initial-user-provided-step.md)
- [EC-38 — Final Acceptance Step](points/EC-38-final-acceptance-step.md)
- [EC-39 — Final Rule](points/EC-39-final-rule.md)
