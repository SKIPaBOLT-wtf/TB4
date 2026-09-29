# IP-66 Evidence E-001 - Independent Linux desktop bundles

Date: 2026-09-29.

Development head: `1269d2ebfb1e91223f1a8d125e5915b0233a2f47`.
PR integration checkout: `2730e33126f726ccab8686c90144a6d2222497b6`.
Verified run:
https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36619412954

Linux job `109580674235` completed successfully on Ubuntu 22.04: native desktop
tests, full Linux regression suite, both actual PyInstaller builds, packaged
application/installer acceptance and artifact publication. This does not claim
execution on a private Linux host.

## Actual products

Separate role archives contain the self-contained application and per-user
install/uninstall scripts. Python, Qt dependencies and canonical runtime data are
bundled. Compatible host graphics/system libraries remain prerequisites.

Artifact ID: `11057008722`.
Name: `tb4-desktop-Linux-2730e33126f726ccab8686c90144a6d2222497b6`.
GitHub-reported ZIP SHA-256:
`8a9e451a3c450b657872196a93e42e1a4015ee2892edb95f5f9de1f60d783f31`.

The artifact contains both installers, checksums and an acceptance report. The
connector returned a downloaded archive, but the subsequent local container read
failed with a tool ClientError. No independent local Linux ZIP hash/readback is
claimed. Native CI acceptance/publication were verified separately through the
completed job record.

## Verification and isolation

Actual acceptance checks frozen runtime imports, canonical resources, provider
static data and a native child command; opens the Qt GUI without starting work;
installs both applications in an isolated home; and self-tests installed workers.

WATCHDOG is removed first and FETCHER must remain executable and pass self-test.
Both private-profile markers must survive both removals. Additional tests cover
paths containing spaces and refusal to uninstall a role with a failed lock probe.
No sudo, TB3 or service mutation is performed.

Linux upgrades stage/self-test replacement binaries, retain a previous-version
directory and refuse another upgrade until that rollback copy is inspected.
Private profiles are separate from binary directories.

## Limits and rollback

Offscreen GUI/CI evidence is not a private tray or live Drive test. Native-child
checks do not prove every user-installed interpreter. Stop/exit the affected role
before restoring prior binaries/configuration. Preserve the peer and Drive tree.
