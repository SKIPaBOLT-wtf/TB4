# RP-025 A001 - bounded implementation design

Inspect source: `71b8eac7aa8e6df58e32db46094a57a3b60598a0`; dependencies RP005/006/019/022/024 VERIFIED.
Separate an installation's protected local UUID from approved opaque device ID,
alias and existing slot. Require a trusted attestation of the actual installation
and device at an explicitly owner-approved enrollment boundary. A discovered
hostname or network endpoint is not identity proof. No default peer attestation.

FETCHER collects its own native OS/architecture and actual launch entrypoint,
bounded allowlisted interpreter availability/version evidence and effective
RP011 polling/idle mode, next-check and clock/freshness information. Local
enabled/disabled execution and interpreter choices stay explicit; the report
alone never grants execution. WATCHDOG selects no remote platform or capability.

Extend only existing catalogue bodies with a closed compact enrollment and actual
profile. Keep artifact/discovery/BALLPARK fields, slot generations and all work/
result/cancel/ACK/status/history records. Target status remains reserved for work
status. Full record/layout byte budgets still apply before durability or writes.
Maximum valid fields may exhaust headroom; reject without changing authority,
records or allocations rather than growing budgets or truncating evidence.

Owner WATCHDOG coordinates approval and subsequent verified same-installation
reports under the existing owner/forced-request checks and one CAS. Duplicate
same binding is inspection/idempotent; reinstallation, device change, alias
conflict or another occupied slot requires explicit maintenance, not takeover
by a copied token. Keep distinct enrollment/profile revisions. Newer reports
cannot overwrite newer shared revisions; stale/future/untrusted samples remain
truthfully unavailable.

Persist the exact pending operation, compatible original instruction pin and
approval in the existing protected setup frame. Lost reply/restart inspect the
same operation; no resend. Prior active registration survives staging/failure.
Revocation targets only this exact installation/enrollment generation and retains
history/generation, without rewriting unknown work or another installation.

WATCHDOG's allowlisted view joins actual shared FETCHER profile with only its own
installation-bound CredentialResolver's enumerated availability. No credential
handle/path/secret, endpoint/hint, hostname or raw provider error is shared.
Actual real/native protected persistence and OS/Qt qualification remain required;
synthetic authority/peer adapters are explicitly isolated from production.
Default setup activation, real instruction profile and legacy schemas remain
unchanged/unreleased. Integrated UI/runtime/release are later gates.
