# IP-65 Evidence E-001 - Independent Windows installers

Date: 2026-09-29.

Development head: `1269d2ebfb1e91223f1a8d125e5915b0233a2f47`.
PR integration checkout: `7d161781b17edf68802809e0e506d944bcc08eca`.
Verified run:
https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36619412954

Windows job `109580673752` completed successfully: native desktop tests, both
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
Name: `tb4-desktop-Windows-7d161781b17edf68802809e0e506d944bcc08eca`.
ZIP SHA-256:
`212c61ffa6b4182097c3585388fccca72c97eb27fe5e0bbeaa6b4d47d3995433`.

The continuation on 2026-09-29 independently verified the downloaded ZIP digest
against GitHub artifact metadata, both installer byte counts and SHA-256 values
against `SHA256SUMS.txt`, and the separately linked installer copies. The earlier
record contained incorrect installer hashes/sizes, job ID and checkout identity;
they are corrected here. Machine-readable readback: `E-002-artifact-readback.json`.
This corrects evidence metadata; it does not replace or rebuild the installers.

| Installer | Bytes | SHA-256 |
|---|---:|---|
| TB4-watchdog-0.0.1-windows-x64-setup.exe | 60065395 | 7cf42687f6c51bdb68e5f30d68aa96e92b7571fd0ca72e2f1713441197e10ada |
| TB4-fetcher-0.0.1-windows-x64-setup.exe | 60050288 | 9711480c88836e65363882d062c82c906c38b397d0bcb5888a5e6b469d4e127d |

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
