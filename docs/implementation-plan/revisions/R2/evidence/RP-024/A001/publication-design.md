# RP-024 bounded publication unit

Base runtime/test source: `6c341da01ddf2e01b45a6aa078e47a9a64754cee`.

RP009 gives global.registry4096, global.settings4096 and target catalogue1024
bytes including key/envelope. RP019 seeds settings UNCONFIGURED and catalogue
artifact bindings/enrollment; RP023 owns nested discovery. Do not replace those
fields, grow budgets, create objects or use artifact buffers for control.

Publish one atomic RecordMutation containing: compact selected device properties
in each existing catalogue's `ballpark` member; revision/selected slot indices,
shared descriptor digest, compatible instruction and exact owner-decision
provenance in global.registry; timing plus matching revision in global.settings.
Use enumerated compact arrays only; reconstruct full shared RP005 descriptor from
the same validated authority snapshot and existing opaque discovery ID/alias.
Absent capability/health proof stays UNKNOWN. The registry declares this compact
codec explicitly. Validate complete serialized budgets; reject overflow before
saving/sending a mutation. No reduced/truncated publication fallback.

Protect commissioning identity and preserve catalogue artifacts/enrollment/
discovery and every unrelated record. Require selected discovery IDs already
published and unchanged. Require exact previous revision/digest; preserve UNKNOWN
jobs without touching work/result/cancel/ACK/history. RP023 must preserve the new
member and reject tampered persisted discovery plans that change it.

The protected setup frame saves exact source/owner decision and frozen operation
before START, with current WATCHDOG capability/owner/force and fresh instruction
checks immediately before write. Restart is INSPECT only. Confirm the same
published descriptor/digest before updating the active local descriptor; local
persist failure leaves a durable pending inspection, never causes a repeat.
Read-only confirmation may prove an already applied transition after takeover;
a different/newer revision remains unresolved and cannot be overwritten by the
old owner. The default installer still supplies DenyActivation; no live release.

Qualification: actual native Docs CAS adapter over synthetic service; lost reply,
local failure, concurrent owner/force, newer revision, wrongroot, wrongschema,
record overflow, unrelated UNKNOWN preservation, restart, revocation, native
protected files and desktop integration handoff. Actual release/live migration
remain separate later acceptance gates.
