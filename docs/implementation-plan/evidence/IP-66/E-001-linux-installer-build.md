# IP-66 Evidence E-001 - Independent Linux desktop bundles

Date: 2026-09-29.

Development head: `1269d2ebfb1e91223f1a8d125e5915b0233a2f47`.
PR integration checkout: `7d161781b17edf68802809e0e506d944bcc08eca`.
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
Name: `tb4-desktop-Linux-7d161781b17edf68802809e0e506d944bcc08eca`.
GitHub-reported ZIP SHA-256:
`c0622f58e6a859e8795eb4b735af8c6dc31da3a0f23545e98c3ebfa608f1471c`.

The artifact contains both installers, checksums and an acceptance report. The
connector returned a downloaded archive, but the subsequent local container read
failed with a tool ClientError during the original continuation.

Follow-up on 2026-09-29 successfully read the archive, verified its ZIP digest
against GitHub metadata, checked both product hashes and read `acceptance.json`.
The previously transcribed ZIP hash and checkout identity were incorrect and are
corrected above. Exact readback is in `E-002-artifact-readback.json`. The earlier
read limitation is historical, not the current verification state. No native test
was rerun by this byte-level check.

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
