# WATCHDOG and FETCHER desktop quick start

Read `DESKTOP.md` for the role-isolation and safety contract. Completion status
lives in `implementation-plan/manifest.yaml`; build evidence and private-pilot
evidence are separate.

## Two applications, one selected control plane

**TB4 WATCHDOG** and **TB4 FETCHER** install independently. Each has its own tray
icon, process, configuration, log and uninstall entry. Install both for a same-host
test, or only the role required on a host. Both configurations must reference the
same deliberately selected existing Google Drive root.

Desktop mode is a per-user alternative to the existing service packaging, not a
replacement for TB3. Do not run a desktop worker and a legacy service for the same
role. Startup refuses an installed matching legacy service; it does not stop,
uninstall or migrate that service. Desktop workers run with the signed-in user's
permissions and do not run before sign-in.

## Windows

The Desktop workflow produces separate installers:

- `TB4-watchdog-0.0.1-windows-x64-setup.exe`
- `TB4-fetcher-0.0.1-windows-x64-setup.exe`

Use artifacts from the exact reviewed build with `SHA256SUMS.txt` and
`acceptance.json`. Python and application dependencies are bundled; a source
checkout and a separate Python installation are not required. These development
installers are unsigned. A checksum verifies the selected build's bytes, not a
publisher signature.

Run each selected installer as the normal user. Default binary locations are
`%LOCALAPPDATA%\Programs\TB4\watchdog` and
`%LOCALAPPDATA%\Programs\TB4\fetcher`. Opening at sign-in is an optional,
initially unchecked installer task. Installation does not start remote work.

Open each application's Start-menu entry. Private profiles are separate under
`%LOCALAPPDATA%\TB4\watchdog` and `%LOCALAPPDATA%\TB4\fetcher`.
Do not copy one role's whole profile into the other.

## Linux

Extract the selected role archive and run `sh install.sh` inside its extracted
`TB4-watchdog` or `TB4-fetcher` directory. To opt into opening that tray app at
sign-in, use `sh install.sh --autostart`. Do not run the installer with sudo.

Binaries live under `${XDG_DATA_HOME:-$HOME/.local/share}/tb4-apps/ROLE`; private
profiles live under `${XDG_DATA_HOME:-$HOME/.local/share}/tb4/ROLE`. Menu entries
are role-specific. Bundles include Python and Qt but still require compatible
standard host graphics/system libraries. The workflow and evidence identify the
tested OS. Without a desktop tray the application keeps a visible window rather
than leaving an invisible, uncontrollable worker.

## First-run configuration

In **Configuration**, edit the role identity and deployment values. The full TOML
editor preserves comments and extension fields. Field buttons accept an existing
Drive folder ID/URL, select a local OAuth client JSON and optionally select a
locally mounted Drive folder. That optional local path is not an API object ID
and is never proof that a remote write has synchronized.

WATCHDOG needs its coordinator ID and each target's explicit ID/key, OS family
and address hints. FETCHER's identity must match the intended registered target.
For an already-online same-host test, WOL and SSH bootstrap can remain explicitly
disabled. This does not test either remote capability.

Each role defaults to its own private token path. Select the correct local OAuth
client and authorize each role explicitly; do not copy another device's token
or identity as a shortcut. The API authorization described in
`GOOGLE_DRIVE_SETUP.md` is required even when a separate Drive desktop application
has mounted a local folder.

Use **Save and validate**. Invalid input does not replace the saved file. A
concurrent on-disk change causes a reload-required conflict instead of blind
overwrite. Replacement retains `config.previous.toml`. Saving is refused while
the role's worker holds its profile lock.

Use **Authorize Drive** for the local browser authorization. **Check Drive and
map** inspects the saved root/map without creating them. For an intentionally
selected existing but uninitialized root, WATCHDOG's **Initialize selected root**
action requires confirmation and uses the production bootstrap helper. It does
not create a second root.

Start WATCHDOG first so it can register its configured targets, then start the
intended FETCHER. `start_role = false` requires explicit Start. Setting it true
opts into starting the role when its tray app opens. Opening at sign-in and
starting a role are distinct settings.

## Monitoring and troubleshooting

Status distinguishes process lifecycle, startup stage, last API outcome, response
age and the last observed canonical protocol name. **RUNNING** means the role
loop was entered, not that every target or the whole control plane is healthy.
**UNKNOWN** means no API observation exists; **STALE** means observations are too
old. **RECENT_RESPONSE** means only that a recent API operation returned: read
its outcome too. Mutation receipts are not shown as confirmed remote metadata.
Monitoring observes existing calls rather than adding Drive polling.

Configuration, authorization, root/map access, service conflicts and runtime
failures have separate stages/codes. Event history is bounded. Safe diagnostic
export includes only allowlisted observations, never the TOML, token contents,
command payloads, object IDs, environment or raw provider errors. Keep separately
collected private runtime evidence outside public issue reports.

## Stop, restart and recovery

**Stop safely** requests cooperative shutdown through a private pipe. FETCHER
uses its existing cancellation/result path; cancelled work may already have
partial effects. The UI waits for confirmed exit. An explicit restart follows
successful exit only. An unconfirmed stop is displayed as unconfirmed, not as a
successful restart. There is no automatic replay, protocol reset or worker
force-kill to clear the display.

Closing the window hides it when a tray exists. **Exit this role application**
is a separate tray action and cooperatively stops an active worker. The peer role
is unaffected. If the GUI pipe disappears, the worker requests cooperative stop;
a blocked provider operation can still need its bounded timeout.

Inspect uncertain-effect jobs before submitting new work. Do not delete/recreate
the Drive tree to clear red or stale status.

## Upgrade, removal and rollback

Stop the affected worker and exit its tray app first. Retain the previous
installer/archive. Installers refuse an in-use default profile rather than
forcibly terminating it. Advanced custom `--profile-root` instances must also
be stopped explicitly before replacing their binaries.

Windows has one uninstall entry per role. Linux's installed role directory
contains `uninstall.sh`. Removal preserves private profiles and the peer role.
Linux upgrades retain a `.previous` binary directory and refuse another upgrade
until that rollback copy has been inspected. No installer removes the Drive root.

To roll back, stop/exit the role, restore previous binaries from the retained
installer/bundle and explicitly restore the required configuration while stopped.
**Restore previous** validates the backup rather than blindly copying it. Do not
replace the peer's identity, token, configuration or logs.

## Build verification is not a private pilot

The Desktop workflow runs native Windows/Linux desktop tests, compiles both
products, checks packaged imports/resources and a native child command, opens
the packaged GUI without starting work, and exercises actual installation/removal
in an isolated test profile. Installers, checksums and acceptance reports are
published only after those checks succeed.

These checks do not prove the owner's interactive tray, private OAuth browser
flow, real Drive round trips, target jobs or wake/bootstrap. IP-68 owns the first
same-host private test; IP-69 separately owns independent-machine expansion.
Neither is completed by building an installer.
