# IP-09 Evidence - Canonical Drive Tree Blueprint

Date: 2026-09-25

## Verified

- The configured TB4 root is explicitly marked `never_auto_recreate`.
- Root children include START_HERE, PARK_MAP, GENESIS, SETTINGS, DOG_HOUSE, BALL_PARK, STRAY_YARD, and DOG_POUND.
- Every registered device receives a deterministic per-device subtree.
- Protocol v1 provides exactly one FETCH_BALL and one STOP_BALL work channel per device.
- Different device folders remain independent work threads.
- TOY_BOX and BONEYARD are explicitly outside the live control path.
- Device folder keys do not auto-rename when hostname changes.
- Logical-object references in the blueprint resolve to the canonical object registry.
- Required static nodes carry explicit repair policy.
- GitHub Actions CI run `36194706773` completed successfully for commit `4b63e6b7f7630082c0e02a0fb9cd81b3efe9b38d`.

## Result

IP-09 completion criteria are satisfied.
