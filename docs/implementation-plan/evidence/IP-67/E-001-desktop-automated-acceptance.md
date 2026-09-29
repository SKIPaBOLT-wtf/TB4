# IP-67 Evidence E-001 - Desktop automated acceptance

Date: 2026-09-29.

Tested development head: `1269d2ebfb1e91223f1a8d125e5915b0233a2f47`.
Tested PR integration checkout: `7d161781b17edf68802809e0e506d944bcc08eca`.

Both native platform jobs completed successfully:
https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36619412954

The original CI workflow for that development head also completed successfully:
https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36619412988

## Evidence reviewed

- IP-63 E-001: role profiles, OS locks, safe configuration replacement/backup,
  bounded observations and diagnostic filtering.
- IP-64 E-001: tray interfaces, responsive worker control, real GUI-to-worker
  saves and production runtime/validator integration.
- IP-65 E-001: actual Windows installers, native acceptance, independent local
  installer hash verification and removal/profile isolation.
- IP-66 E-001: actual Linux bundles/installers, native acceptance and isolation;
  the initial local archive-read limitation and successful follow-up are recorded.

The matrix installs GUI/provider dependencies before desktop tests, so these
checks exercise PySide6 and production imports rather than treating local skips
as coverage. Platform-specific skips do not prove execution on the other OS.
Linux also runs the complete regression suite. Original CI includes the public
repository security scan.

Distribution acceptance uses actual built/installed applications, not only
installer source. Upload occurs only after acceptance passes. Bundle resources
come from tracked source/config/protocol files, not private untracked directories.

## Evidence metadata correction - 2026-09-29

A subsequent byte-level readback found transcription errors in the original
checkout identity, Windows job/product metadata, Linux ZIP digest and original
CI run link. These fields are corrected in IP-64..IP-67; prior values remain in
Git history. IP-65 and IP-66 each include `E-002-artifact-readback.json` with
independently computed hashes matching the provider and bundled checksums.
The installers were not rebuilt or changed. This is not a new native CI run or
a private pilot, and no implementation status was advanced by this correction.

## Development acceptance

The requested public desktop development is ready for private testing: independent
role installers on Windows/Linux; separate trays/profiles/controls/uninstall
identities; validated config saves, conflicts, backups and explicit restore;
process/API observation distinction; bounded logs and safe diagnostics; cooperative
stop/restart without automatic replay or root reset; and native package acceptance.

`docs/DESKTOP_QUICKSTART.md` provides first-run and rollback instructions.
Final documentation changes do not replace the exact tested binaries identified
by the commit and artifact records above.

## Not accepted by this record

No private workstation was inspected, configured or modified. No private OAuth
browser flow, real Drive round trip, target command, wake/bootstrap, owner's
interactive tray or private failure recovery is claimed.

The next step is IP-68, the owner-selected same-host private pilot. IP-69 remains
independent-machine testing and IP-70 expanded final acceptance. Neither pilot nor
final system acceptance is completed by desktop CI.

## Rollback

Revert desktop feature commits to restore the prior public core/service surface.
For a later deployment, use role-specific binary/config rollback while preserving
private state; never reset the Drive root automatically.
