# Independent WATCHDOG and FETCHER desktop applications

## Scope and ordering

The owner requested independently installable WATCHDOG and FETCHER applications,
each with its own system-tray interface for configuration, monitoring and
troubleshooting. Finish desktop development and build verification before the
first private workstation test. Both roles may run on that workstation.

A same-host test is not evidence of an independent two-machine pilot. Keep that
later acceptance gate, its historical records and the protocol vocabulary intact.
Private machine names, mounted-drive letters, root IDs and OAuth data do not
belong in this repository.

## Two applications, not two control planes

Each role has its own installer, executable/launcher, tray icon, local profile,
configuration, process lock, diagnostic log and uninstall entry. Installing,
starting, stopping or removing one must not operate on the other's files or
processes. The shared implementation is an internal library, not a mandatory
second installed application.

The existing service/CLI interfaces remain supported. Desktop mode is an
explicit per-user alternative; do not run a legacy service and a desktop worker
for the same role/identity simultaneously. The desktop worker runs as the signed-in
user, never silently as an elevated account or LocalSystem. Existing TB3 is not
replaced, repaired or used as an installation prerequisite.

WATCHDOG and FETCHER retain their existing responsibilities. Selecting the
coordinator's own host as a target does not merge those roles. The coordinator
identity and target identity remain explicit, and both configurations reference
one deliberately selected existing Drive root. WOL and SSH may be explicitly
disabled for an already-online same-host test; do not claim those paths were tested.

## Configuration

Provide a first-run configuration editor, validation before saving, credential
file selection, explicit OAuth authorization and an explicit tree-initialization
action using the production bootstrap helper. Preserve unknown TOML fields and
comments. Saving uses an expected-content digest, an atomic replacement and a
backup; reject concurrent changes and editing while a worker holds its lock.
Configuration files and OAuth tokens remain private and outside source control.

A mounted/synchronized Drive folder is an optional local convenience. A local
path is not a stable Drive object ID, and a local write is not remote confirmation.
The API backend and verified production helpers remain authoritative. Selecting
such a folder must not quietly select a different root or enable a sync-only
backend. Missing mount visibility and missing API authorization are distinct
checks.

## Monitoring and troubleshooting

Show process lifecycle, last observed Drive operation/result, observation age,
known protocol state and a bounded local event history. A running process does
not prove remote health. Expired or absent observations must read stale/unknown,
not green. Observe production I/O without extra Drive polling or folder scans.

The UI event loop never performs network work, sleeps, waits for child completion
or runs long configuration checks. User actions run in a separate worker process.
Stop is cooperative through a private pipe, including FETCHER's existing
cancellation path. Restart waits for confirmed exit. Do not automatically replay
work, reset protocol objects or force-kill an active job to make the UI look healthy.
Closing the main window hides it to the tray; exiting is a distinct action.

Diagnostics are a whitelisted JSON report, not a copy of configuration, request
payloads, raw provider errors, tokens or environment variables. No listening
network administration endpoint is introduced. Failure messages must distinguish
configuration, authorization, root/map access, role startup and runtime failure.

## Distribution and verification

Produce independent Windows installers and Linux desktop bundles/installers for
both roles. Include the runtime dependencies and canonical protocol/default data.
Installation must not require the source checkout or a preinstalled Python.
Installers do not start remote work before configuration and explicit Start.
Preserve private configuration on uninstall and preserve the peer role.

Test configuration concurrency, rollback, role isolation, malformed telemetry,
stale observations, failed startup, cooperative stop, double launch and missing
tray support. Test both GUI instances and packaged resource access on Windows and
Linux. Build artifacts and checksums are separate from public completion evidence.
An installer source file alone is not a built or tested installer.

## Rollback

Before upgrades, stop the affected worker and exit its tray application. Keep the
previous installer/bundle. Reinstall the previous version to roll back binaries;
configuration backups are restored explicitly while the role is stopped. Never
roll back by deleting the Drive root, copying another device's identity, or
replaying an operation whose effects are unknown.
