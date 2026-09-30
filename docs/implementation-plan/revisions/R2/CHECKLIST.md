# R2 executable checklist

64 steps; 256 individually identified checks. All implementation steps are initially PLANNED.

This is a projection of `manifest.yaml`. Mark a step/check complete only through a journaled evidence-backed manifest update; never tick this index independently. Detailed checkboxes and verification boundaries are in each linked step.

## Contracts, privacy, continuation and defect reproduction

- [x] [RP-001 - Enforced development-ledger contract](steps/RP-001.md) - prerequisites: none.
- [x] [RP-002 - Checkpoint publication and cold-resume helper](steps/RP-002.md) - prerequisites: RP-001.
- [x] [RP-003 - Defect provenance and re-openable verification](steps/RP-003.md) - prerequisites: RP-001, RP-002.
- [x] [RP-004 - Privacy classification and safe evidence policy](steps/RP-004.md) - prerequisites: RP-001.
- [x] [RP-005 - Topology-neutral BALLPARK and capability schema](steps/RP-005.md) - prerequisites: RP-004.
- [x] [RP-006 - Credential-reference resolver contract](steps/RP-006.md) - prerequisites: RP-004, RP-005.
- [x] [RP-007 - Repository instruction-version and trust contract](steps/RP-007.md) - prerequisites: RP-004, RP-005.
- [x] [RP-008 - Storage exclusion and failover feasibility gate](steps/RP-008.md) - prerequisites: RP-004, RP-005.
- [x] [RP-009 - Fixed exchange layout and capacity contract](steps/RP-009.md) - prerequisites: RP-005, RP-008.
- [x] [RP-010 - Command status and ownership protocol contract](steps/RP-010.md) - prerequisites: RP-007, RP-008, RP-009.
- [ ] [RP-011 - Timing semantics and relationship validation](steps/RP-011.md) - prerequisites: RP-005, RP-010.
- [ ] [RP-012 - Security and failure semantics decision gate](steps/RP-012.md) - prerequisites: RP-004, RP-006, RP-010, RP-011.
- [ ] [RP-013 - Reproduce ordinary result-publication conflict](steps/RP-013.md) - prerequisites: RP-001, RP-003, RP-004.
- [ ] [RP-014 - Reproduce cancellation versus natural-exit race](steps/RP-014.md) - prerequisites: RP-001, RP-003, RP-004.

## Storage, ownership, commissioning primitives and credentials

- [ ] [RP-015 - Race-safe exact-object mutation and verification](steps/RP-015.md) - prerequisites: RP-008, RP-010, RP-012, RP-013.
- [ ] [RP-016 - Shared leadership lease and fencing primitive](steps/RP-016.md) - prerequisites: RP-008, RP-010, RP-012, RP-015.
- [ ] [RP-017 - WATCHDOG incumbent-first startup and standby](steps/RP-017.md) - prerequisites: RP-011, RP-016.
- [ ] [RP-018 - Shared-folder transport conformance adapter](steps/RP-018.md) - prerequisites: RP-008, RP-009, RP-010, RP-012, RP-015.
- [ ] [RP-019 - Idempotent fixed-slot commissioning](steps/RP-019.md) - prerequisites: RP-009, RP-015, RP-016.
- [ ] [RP-020 - Windows protected credential resolver](steps/RP-020.md) - prerequisites: RP-006, RP-012.
- [ ] [RP-021 - Linux protected credential resolver](steps/RP-021.md) - prerequisites: RP-006, RP-012.

## First run, BALLPARK, enrollment and reconfiguration

- [ ] [RP-022 - First-run commissioning state machine](steps/RP-022.md) - prerequisites: RP-005, RP-007, RP-011, RP-012, RP-017, RP-019, RP-020, RP-021.
- [ ] [RP-023 - Scoped discovery and persistent catalogue identity](steps/RP-023.md) - prerequisites: RP-005, RP-012, RP-017, RP-022.
- [ ] [RP-024 - Private BALLPARK creation with SKILL assistance](steps/RP-024.md) - prerequisites: RP-005, RP-007, RP-019, RP-022, RP-023.
- [ ] [RP-025 - FETCHER enrollment and effective profile publication](steps/RP-025.md) - prerequisites: RP-005, RP-006, RP-019, RP-022, RP-024.
- [ ] [RP-026 - Authorized stable-IP provisioning adapter](steps/RP-026.md) - prerequisites: RP-006, RP-012, RP-020, RP-021, RP-023, RP-024.
- [ ] [RP-027 - Reconfiguration of an existing deployment](steps/RP-027.md) - prerequisites: RP-011, RP-017, RP-022, RP-024, RP-025.
- [ ] [RP-028 - Explicit full reset and re-enrollment](steps/RP-028.md) - prerequisites: RP-006, RP-012, RP-019, RP-025, RP-027.
- [ ] [RP-029 - Ongoing BALLPARK evolution and stale-view handling](steps/RP-029.md) - prerequisites: RP-007, RP-023, RP-024, RP-025, RP-027.
- [ ] [RP-030 - Interrupted commissioning and maintenance acceptance](steps/RP-030.md) - prerequisites: RP-019, RP-022, RP-024, RP-025, RP-027, RP-028, RP-029.

## WATCHDOG ingress, status, routing, wake and acknowledgement

- [ ] [RP-031 - AUTO-SNIFF admission validator](steps/RP-031.md) - prerequisites: RP-010, RP-012, RP-015, RP-025.
- [ ] [RP-032 - Common ingress reservation and durable receipts](steps/RP-032.md) - prerequisites: RP-009, RP-010, RP-015, RP-016, RP-031.
- [ ] [RP-033 - Deterministic routing and target busy exclusion](steps/RP-033.md) - prerequisites: RP-025, RP-029, RP-031, RP-032.
- [ ] [RP-034 - Unified command and device status projection](steps/RP-034.md) - prerequisites: RP-005, RP-010, RP-025, RP-029, RP-032, RP-033.
- [ ] [RP-035 - WATCHDOG activity-aware network scheduler](steps/RP-035.md) - prerequisites: RP-011, RP-017, RP-023, RP-034.
- [ ] [RP-036 - Windows deterministic SSH status/start helper](steps/RP-036.md) - prerequisites: RP-006, RP-012, RP-020, RP-022, RP-025.
- [ ] [RP-037 - Linux deterministic SSH status/start helper](steps/RP-037.md) - prerequisites: RP-006, RP-012, RP-021, RP-022, RP-025.
- [ ] [RP-038 - Nonblocking readiness and wake coordination](steps/RP-038.md) - prerequisites: RP-011, RP-017, RP-025, RP-033, RP-034, RP-036, RP-037.
- [ ] [RP-039 - Delivery expiry and late-claim reconciliation](steps/RP-039.md) - prerequisites: RP-010, RP-011, RP-015, RP-016, RP-033, RP-038.
- [ ] [RP-040 - Result-consumption acknowledgement and recycling](steps/RP-040.md) - prerequisites: RP-009, RP-010, RP-015, RP-032, RP-033, RP-039.

## FETCHER lifecycle, native execution, cancellation and return

- [ ] [RP-041 - FETCHER fast and slow polling lifecycle](steps/RP-041.md) - prerequisites: RP-011, RP-025, RP-034, RP-040.
- [ ] [RP-042 - FETCHER exit mode and wake launch integration](steps/RP-042.md) - prerequisites: RP-011, RP-025, RP-036, RP-037, RP-038, RP-041.
- [ ] [RP-043 - FETCHER claim and durable execution identity](steps/RP-043.md) - prerequisites: RP-010, RP-012, RP-015, RP-025, RP-033, RP-039, RP-041.
- [ ] [RP-044 - Windows RUNNER supervision and termination](steps/RP-044.md) - prerequisites: RP-012, RP-014, RP-043.
- [ ] [RP-045 - Linux RUNNER supervision and termination](steps/RP-045.md) - prerequisites: RP-012, RP-014, RP-043.
- [ ] [RP-046 - Cancellation transport and execution reconciliation](steps/RP-046.md) - prerequisites: RP-010, RP-012, RP-014, RP-032, RP-038, RP-043, RP-044, RP-045.
- [ ] [RP-047 - Durable result outbox and restart recovery](steps/RP-047.md) - prerequisites: RP-012, RP-015, RP-043, RP-044, RP-045, RP-046.
- [ ] [RP-048 - Reliable ordinary terminal publication](steps/RP-048.md) - prerequisites: RP-010, RP-015, RP-034, RP-040, RP-047.
- [ ] [RP-049 - Reusable script and output artifact slots](steps/RP-049.md) - prerequisites: RP-009, RP-012, RP-019, RP-043, RP-047, RP-048.
- [ ] [RP-050 - Bounded history retention and quarantine](steps/RP-050.md) - prerequisites: RP-009, RP-012, RP-019, RP-040, RP-047, RP-049.

## Repository instructions, pointer SKILL, interfaces and installers

- [ ] [RP-051 - Repository-owned operational SKILL and helper interface](steps/RP-051.md) - prerequisites: RP-007, RP-024, RP-029, RP-032, RP-034, RP-038, RP-040, RP-046, RP-048, RP-049.
- [ ] [RP-052 - Pointer-only installed SKILL package](steps/RP-052.md) - prerequisites: RP-007, RP-051.
- [ ] [RP-053 - WATCHDOG GUI catalogue leadership and configuration](steps/RP-053.md) - prerequisites: RP-017, RP-022, RP-024, RP-027, RP-028, RP-029, RP-034, RP-035, RP-038.
- [ ] [RP-054 - FETCHER GUI execution and idle-policy monitoring](steps/RP-054.md) - prerequisites: RP-022, RP-025, RP-027, RP-028, RP-034, RP-041, RP-042, RP-043, RP-046, RP-047, RP-048.
- [ ] [RP-055 - Independent Windows installers and upgrade checks](steps/RP-055.md) - prerequisites: RP-020, RP-022, RP-030, RP-036, RP-042, RP-049, RP-050, RP-053, RP-054.
- [ ] [RP-056 - Independent Linux installers and upgrade checks](steps/RP-056.md) - prerequisites: RP-021, RP-022, RP-030, RP-037, RP-042, RP-049, RP-050, RP-053, RP-054.

## Migration, adversarial acceptance, releases and real pilots

- [ ] [RP-057 - Legacy pilot-state migration and failure preservation](steps/RP-057.md) - prerequisites: RP-010, RP-015, RP-019, RP-027, RP-028, RP-040, RP-047, RP-048, RP-050, RP-055, RP-056.
- [ ] [RP-058 - Integrated interruption concurrency and rate suite](steps/RP-058.md) - prerequisites: RP-015, RP-017, RP-018, RP-019, RP-030, RP-033, RP-035, RP-038, RP-039, RP-040, RP-042, RP-043, RP-046, RP-048, RP-049, RP-050.
- [ ] [RP-059 - End-to-end privacy and supply-chain acceptance](steps/RP-059.md) - prerequisites: RP-004, RP-006, RP-012, RP-020, RP-021, RP-024, RP-026, RP-027, RP-028, RP-049, RP-050, RP-051, RP-052, RP-055, RP-056.
- [ ] [RP-060 - Portability and topology compatibility acceptance](steps/RP-060.md) - prerequisites: RP-018, RP-023, RP-024, RP-025, RP-026, RP-029, RP-030, RP-035, RP-036, RP-037, RP-038, RP-041, RP-042, RP-055, RP-056, RP-058, RP-059.
- [ ] [RP-061 - Coordinated release and repository instruction publication](steps/RP-061.md) - prerequisites: RP-007, RP-051, RP-052, RP-055, RP-056, RP-057, RP-058, RP-059, RP-060.
- [ ] [RP-062 - Authorized same-host real-provider pilot](steps/RP-062.md) - prerequisites: RP-030, RP-055, RP-056, RP-057, RP-058, RP-059, RP-060, RP-061.
- [ ] [RP-063 - Independent-machine fallback and lifecycle pilot](steps/RP-063.md) - prerequisites: RP-017, RP-018, RP-026, RP-028, RP-057, RP-058, RP-059, RP-060, RP-061, RP-062.
- [ ] [RP-064 - Final traceable acceptance and operational handoff](steps/RP-064.md) - prerequisites: RP-001, RP-002, RP-003, RP-058, RP-059, RP-060, RP-061, RP-062, RP-063.
