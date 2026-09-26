# IP-27 Evidence - GENESIS Tree Bootstrap

Date: 2026-09-26

## Verified

- Bootstrap requires an explicitly selected existing root and never creates a second TB4 root implicitly.
- Fresh bootstrap creates the canonical static root tree, initial WATCHDOG control objects, GENESIS metadata, and PARK_MAP.
- Bootstrap reuses a safely partial tree and does not duplicate canonical children.
- A second bootstrap performs no redundant object creation and avoids rewriting an unchanged PARK_MAP.
- Duplicate canonical children fail closed instead of being guessed.
- Ambiguous create outcomes are reconciled by maintenance enumeration before proceeding.
- WATCHDOG identity is not invented during bootstrap.
- GENESIS stores only public protocol/bootstrap metadata.
- The bootstrap CLI rejects a missing explicit root and supports the deterministic in-memory validation backend.
- GitHub Actions CI run `36199442790` completed successfully for commit `621c5fdd733ea0f126e70cc154d71cc8fe46fd7d`.

## Result

IP-27 completion criteria are satisfied.
