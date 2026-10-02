# Isolated Linux installer inspection-failure reproduction

INTENT: RP-026-A001-0026.
Source: f7982df61404257affa794c4c355cdba3841d305
Actual checkout: 792465e261a2f2b303ef7f7283f389cb26e40cf7; installer scripts were verified unchanged relative to source.
Platform: actual Linux through the attached WSL Ubuntu environment; no claim of live deployment acceptance.

Reproduction: for each existing install/uninstall script, create fresh synthetic HOME/XDG, table under a custom installation-local leaf and dummy role binaries. Prepend an isolated find shim that exits 42 with empty output. This represents an unavailable table search; it does not inspect or alter any real installation. Run the exact script with fixed WATCHDOG substitution. Record closed shell status and byte-preservation facts.

- install: script exit 0, original table and binaries retained = false, refused before mutation = false.
- uninstall: script exit 0, original table and binaries retained = false, refused before mutation = false.

The diagnostic invariant failed for both operations. POSIX command substitution is evaluated inside the -z test; a nonzero find exit with empty output becomes a successful empty-string test, so set -e does not stop the operation. The prior default-leaf guard still catches its own known path; the new custom-table search lacks a trustworthy absence result. This new RP-026 regression is DEF-051, and no predecessor/live installation is claimed broken.

Required fix: explicitly capture/check the search status before testing the output; closed failure text without path output, then refuse before any replacement/removal. Add isolated error-propagation regression for both operations. Keep the legitimate data-present/no-data coverage and original history. RP-026 C1-C4/DEF-049/050/051 remain unaccepted pending exact-source native/Qt/Linux/build/privacy qualification.

The scripts changed only these newly created synthetic fixture trees. Raw output and fixtures remain task-owned locally. No user's table/binaries/profile/credential/router/service was accessed or changed. Outer cleanup exit is not qualification; the per-script exits and preserved-byte facts establish the failure.
