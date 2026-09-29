# IP-67 Evidence E-001 - Desktop automated acceptance

Date: 2026-09-29.

Tested development head: `1269d2ebfb1e91223f1a8d125e5915b0233a2f47`.
Tested PR integration checkout: `2730e33126f726ccab8686c90144a6d2222497b6`.

Both native platform jobs completed successfully:
https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36619412954

The original CI workflow for that development head also completed successfully:
https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36619412977

## Evidence reviewed

- IP-63 E-001: role profiles, OS locks, safe configuration replacement/backup,
  bounded observations and diagnostic filtering.
- IP-64 E-001: tray interfaces, responsive worker control, real GUI-to-worker
  saves and production runtime/validator integration.
- IP-65 E-001: actual Windows installers, native acceptance, independent local
  installer hash verification and removal/profile isolation.
- IP-66 E-001: actual Linux bundles/installers, native acceptance and isolation;
  its independent local archive-read limitation is explicitly recorded.

The matrix installs GUI/provider dependencies before desktop tests, so these
checks exercise PySide6 and production imports rather than treating local skips
as coverage. Platform-specific skips do not prove execution on the other OS.
Linux also runs the complete regression suite. Original CI includes the public
repository security scan.

Distribution acceptance uses actual built/installed applications, not only
installer source. Upload occurs only after acceptance passes. Bundle resources
come from tracked source/config/protocol files, not private untracked directories.

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
