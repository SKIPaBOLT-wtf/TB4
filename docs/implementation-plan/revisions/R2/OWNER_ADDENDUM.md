# Owner addendum - portable commissioning and repository-owned instructions

Date: 2026-09-30. Applies after DEVELOPMENT_REALIGNMENT_PROMPT.md. The owner now
authorizes detailed planning and a resumable work instruction. This is not yet
permission to implement, install, migrate or test a live deployment.

## Requirements added by the latest instruction

Produce many independently executable/verifiable steps and keep each step's
progress in GitHub at every meaningful boundary, including debugging. A cold
return must identify the interrupted action, last confirmed fact, evidence and
next action. Use the same traceable method to find and correct the step that
introduced a defect; never erase a failed attempt or infer a root cause.

Keep the product portable across systems and network topologies. All real system,
network, storage and credential-binding facts are collected and validated during
installation/first-run commissioning, not embedded in source or generic guides.
After WATCHDOG installation, the repository-loaded SKILL assists the owner and
WATCHDOG in preparing the relevant BALLPARK description. WATCHDOG validates and
publishes the authoritative descriptor. Later controlled evolution and starting
setup again must be supported.

WATCHDOG may keep installation-scoped references to authorized keys/credentials
so fixed helpers can resolve/use them automatically. References are not secret
values and must not encode sensitive paths/accounts/addresses. Secret material
stays in the approved local store; no secret values appear in code, program
descriptions, SKILL text, debug output, GitHub or other product documentation.

The installed ChatGPT/other-LLM SKILL contains no TB4 operational procedure. It
only identifies this public repository and the exact authoritative entry file,
retrieves it and stops if unavailable. The entry can evolve without reinstalling
a copy of the operating manual into every LLM host.

## Necessary engineering clarifications, not invented deployment facts

- Public artifacts contain only generic contracts and synthetic fixtures.
- Real topology lives in a protected operational configuration store, because
  the software must know its environment. It is not copied into public material
  or debug logs. A private LLM-visible BALLPARK projection exposes only needed
  nonsecret aliases/capabilities/timing and safe control references.
- Secret values never belong in either description. Actual resolver handles and
  store/key locations remain protected local bindings; the shared projection can
  say a capability is configured without revealing where/how its key is stored.
- Reconfiguration is not synonymous with destructive reset. Both need staged
  validation, ownership/in-flight-work checks and explicit irreversible limits.
- Fetching current guidance must not mix different schema versions inside an
  already dispatched operation. Resolve current guidance for a new workflow,
  pin the selected compatible revision while it is in flight, and refresh at the
  next workflow/version-change boundary. Incompatible/unavailable sources block.
- No mechanism can write an outcome after an arbitrary crash has already happened.
  Pre-action remote INTENT records make the uncertainty recoverable; resume must
  inspect effects rather than invent completion or repeat a mutation.

No private topology, credential, root identifier or installed profile was read
or changed to produce this planning addendum. Earlier live failure evidence
remains historical and unresolved; the plan does not repair or replay it.

## Later owner direction - 2026-10-02

[RP-026 amendment A-001](amendments/RP-026/A-001-local-network-table.md) records the configurable installation-local network table, observation-only WATCHDOG, deterministic repository-owned device-description SKILL and optional stable-IP status. This replaces the unresolved mandatory provisioning choice; private network-specific administration remains outside public product instructions. Ordinary implementation authority is unchanged.
