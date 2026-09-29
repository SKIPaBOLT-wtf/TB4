# IP-68 Evidence E-001 - Same-host pilot started

Date: 2026-09-30.

The owner-selected Windows workstation began the private same-host desktop pilot
using the exact reviewed Windows desktop build recorded by IP-65/IP-67.

Verified pilot-start facts, intentionally sanitized for the public repository:

- the WATCHDOG installer bytes matched the reviewed SHA-256 before installation;
- the workstation had no pre-existing TB4 desktop executable/profile, TB4 role
  process or TB4 Windows service in the default locations checked before install;
- the selected existing Google Drive root was reachable through authenticated
  Drive API calls;
- a pre-bootstrap check successfully enumerated that root and failed only because
  the required PARK_MAP did not yet exist;
- WATCHDOG initialized the canonical TB4 tree inside that selected existing root;
- independent API readback then observed exactly one PARK_MAP plus the canonical
  top-level GENESIS, SETTINGS, DOG_HOUSE, BALL_PARK, STRAY_YARD, DOG_POUND and
  START_HERE objects;
- no second TB4 root was created and TB3 was not modified.

This is progress evidence only. IP-68 remains IN_PROGRESS until both desktop
roles are installed/configured and the required same-host real-Drive job,
script-artifact, cancellation, failure/recovery and return-to-ready scenarios
are completed and sanitized evidence is reviewed.

Private OAuth paths, token contents, root/object IDs, host identity and other
deployment-specific values are deliberately excluded.
