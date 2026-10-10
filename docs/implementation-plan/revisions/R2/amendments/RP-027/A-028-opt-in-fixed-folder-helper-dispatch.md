# RP-027 amendment A-028 — opt-in fixed Folder helper dispatch

This adds an explicit server forced-command mode to use the qualified probe and
normal authority protocols through one selected key without accepting shell code.
Endpoint attachment and trusted fresh-profile composition remain separate work.

## Independent scheduling and authority

Event384 schedules this helper foundation independently of immutable acc26
request27 qualification. It relies on the already qualified A020/A023/A024/A025
probe and READ/CAS protocols and original helper; it neither invokes nor changes
A026 native endpoint operations or A027 optional pointer semantics. Native
credential scopes retain their separate explicit grants. All tests use synthetic
owned loopback SSH/native fixtures; no live server, key or authorization changes.

## Closed opt-in server mode

The server-local --credential-dispatch flag is mutually exclusive with the old
--commissioning-probe flag. Only exact SSH_ORIGINAL_COMMAND tokens
tb4-folder-probe-v1 and tb4-folder-v1 select the existing VERIFY or READ/CAS
handler. Missing, extra, unknown, whitespace or injected tokens fail before
configuration, stdin or database access. The token is never evaluated or run;
it cannot name a path, executable, mode, operation or alternate configuration.
The dedicated server forced command continues to supply protected config and
mapping-store paths. Timeout8 and MAX_WIRE bounds remain.

Old default normal and explicit probe-only modes keep their meanings and do not
interpret SSH_ORIGINAL_COMMAND. Existing protocol validators continue to reject
command/payload confusion. Normal ACCEPTED requires readback; a lost-after-commit
reply remains UNKNOWN and neither read nor proof repeats CAS.

## Verification and held acceptance

Portable tests cover exact/negative tokens, rejection before IO, one bounded
handler call, mutually exclusive flags, non-Linux refusal and old-mode behavior.
Required actual Linux tests restore the same explicitly dual-purpose protected
native image into the qualified purpose-specific factories, use actual held key
and known-host files through one forced helper, repeat typed first-run proof,
read/CAS/readback, two-client conflict, command confusion, credential loss,
lost reply and stale/forced first-CAS takeover preserving UNKNOWN. Former-owner
or all-peer ACK is unnecessary. Keys, history, profile and file identities stay
private; no saved metadata itself grants proof, routing or activation.

The opt-in fixture argument leaves every original SSH fixture mode unchanged.
New portable/actual cases join required Linux workflow group1. No test result is
claimed by source alone. Native pointer attachment/recovery, trusted fresh Setup
connection, runtime/GUI, declared topology/platform/packages/common gates and
all RP-027.C1-C4 acceptance remain held; default DenyActivation stays closed.

