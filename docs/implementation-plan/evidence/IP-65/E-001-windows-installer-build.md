# IP-65 Evidence E-001 - Independent Windows installers

Date: 2026-09-29.

Development head: `1269d2ebfb1e91223f1a8d125e5915b0233a2f47`.
PR integration checkout: `2730e33126f726ccab8686c90144a6d2222497b6`.
Verified run:
https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36619412954

Windows job `109580674358` completed successfully: native desktop tests, both
actual PyInstaller/Inno builds, packaged application/installer acceptance and
artifact publication.

## Products and isolation

Each role has a fixed-role GUI/worker executable, separate Inno application ID,
per-user binary directory, Start-menu entry and optional logon entry. Neither
source checkout nor separately installed Python is required. Installation does
not install/start a service or automatically start remote work.

Upgrade/removal checks the role's default profile lock and refuses in-use
replacement. Custom profile instances must also be stopped explicitly. Removal
preserves private profiles and the other role.

## Actual artifact verification

Artifact ID: `11058262414`.
Name: `tb4-desktop-Windows-2730e33126f726ccab8686c90144a6d2222497b6`.
ZIP SHA-256:
`212c61ffa6b4182097c3585388fccca72c97eb27fe5e0bbeaa6b4d47d3995433`.

The artifact was downloaded and its ZIP digest independently checked. Both
installers were extracted and hashed against the included `SHA256SUMS.txt`.

| Installer | Bytes | SHA-256 |
|---|---:|---|
| TB4-watchdog-0.0.1-windows-x64-setup.exe | 63646917 | fde6862a6328234e0ad021a0e9b54cfab0fbb32c6d241c8ded11a9af838ce733 |
| TB4-fetcher-0.0.1-windows-x64-setup.exe | 63646892 | 01348cbeed62e572a29aebfc888e1ab783d81e41e53d7921f1f063c651a7b567 |

The downloaded acceptance report records PASS for each role's bundle self-test,
GUI smoke and install/uninstall/profile-isolation scenario, scoped to
`credential-free-platform-CI`.

Acceptance runs actual setup programs and installed worker self-tests, removes
WATCHDOG first, requires FETCHER still to work, then removes FETCHER. Both private
profile preservation markers must survive both removals.

## Limits and rollback

Development installers are unsigned; checksums are not publisher signatures.
No owner workstation, private account authorization or real Drive work was tested.
IP-68 owns those checks. Retain the previous installer/config backup; stop/exit the
affected role before rollback. Never delete the Drive root for rollback.
