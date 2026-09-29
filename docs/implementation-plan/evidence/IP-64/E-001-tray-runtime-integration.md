# IP-64 Evidence E-001 - Tray applications and runtime integration

Date: 2026-09-29.

Tested development head: `1269d2ebfb1e91223f1a8d125e5915b0233a2f47`.
Native Windows/Linux run:
https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36619412954

The PR integration checkout was
`7d161781b17edf68802809e0e506d944bcc08eca`, combining that head with the
unchanged main baseline. Both platform jobs completed successfully.

Correction on 2026-09-29: the checkout identity above now matches the actual
artifact name and CI checkout; the previous value was a transcription error.
This changes metadata only and does not claim a new test run.

## Implemented boundary

Separate fixed-role entrypoints/tray windows use separate profiles, logs and
OS-held locks. The GUI launches a worker with an argument vector, not a shell
command string. Configuration saves, checks, authorization and initialization
run outside the GUI event loop. Existing production factories, ServiceHost,
validators, backend and bootstrap helpers remain authoritative.

Stop is an asynchronous private pipe message bound to the exact child, so it
cannot block the GUI behind a configuration write or stop a later restart.
Restart follows confirmed successful exit. EOF requests cooperative stop. Raw
stdout/stderr is not exported. No root reset, replay, forced worker kill or TB3
modification was added.

The observer records existing backend calls without adding Drive polls. Process
lifecycle, startup stage, response age and outcome remain distinct. Mutation
receipts do not become remote-readback observations. Packaged workers restore
host library-search settings before native subprocess execution.

## Verification

Both native jobs passed the desktop tests with PySide6 and production core
modules installed. Coverage includes two role windows, no initial worker start,
field isolation, real GUI-to-worker config save, failed-save preservation,
cooperative stop, a deliberately blocked writer, duplicate worker launch,
bounded queues, output filtering, EOF and terminal snapshots. Production
validators accept each configured role template; display names come from the
canonical registry. POSIX-specific tests are not claimed on Windows.

The first Windows test run exposed LF/CRLF conversion in a fixture. Explicit
fixture bytes and both line-ending cases fixed the test without weakening the
production conflict check. The final matrix passed those cases.

Actual frozen bundles also passed GUI smoke and runtime/resource/native-child
self-tests during distribution acceptance. Native Qt/offscreen smoke is not an
owner's interactive-tray test. No private OAuth or real Drive work was performed.

## Rollback

Revert desktop feature commits while retaining the preceding core/CLI/service
interfaces. No private deployment rollback was required.
