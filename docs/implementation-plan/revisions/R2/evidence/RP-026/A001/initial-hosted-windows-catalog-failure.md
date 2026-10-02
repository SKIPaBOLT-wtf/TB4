# Initial hosted qualification - Windows catalog byte failure

INTENT: RP-026-A001-0035; STARTED0036, partial milestone0037.
Public semantic source: aba77c9aa9df314e3088dfb388a84a7f7011cb6a.
Qualification head: 9b8a5d8f9baa2047df00fab38d636accacf73a58.
All three jobs checked out 2f848d83a4556e906326ca6a5639b2c29ee6d484; Git tree d57555ec65faf7c76f187fe7fa01d76b5ddf861e equals the head tree and parents main33e7aeb plus qualification head.

- CI37018760949/job110876102889 SUCCESS: 2445 passed, 27 declared skips, four historical strict DEF-002 xfails, 658.45 s. Early native Linux credentials43/protected setup34/loopback2 and scanner passed.
- Progress37018760710/job110876102191 SUCCESS: 235 development tests12.86 s, current/history/scanner passed.
- Desktop37018760515 Linux job110876101105 SUCCESS: desktop90pass4skip; nativeLinux43/protected34/loopback2; BALLPARK75/enrollment79; complete2468pass21skip4 historical strict xfails,705.48 s. WATCHDOG/FETCHER builds, frozen self-tests, GUI/setup and isolated install/uninstall/profile isolation all passed. Linux artifact11233135402,314336604 bytes, provider digest sha256:b396af00052a9790f85e11cfeecf5ffc2f64c2e2dac75e21eefacdb22bd6244e. No large bundle download, live deployment or independent rehash is claimed.
- Desktop Windows job110876101662 FAILURE: desktop74pass20POSIXskips; nativeWindows15/protected30pass4Linuxskips/loopback2; BALLPARK75/enrollment79 passed. Complete suite1failed2381passed107skipped4 historical strict xfails,783.38 s. Both Windows builds/distribution/upload skipped and unqualified.

Failure: tests/coach/test_instruction_selection.py::test_repository_catalog_consistent_but_deliberately_not_live_eligible. Original raw-byte digest assertion unchanged. Catalog expects new guidance LF digest b7528e9003fe9b599845f4261f1760296773a2d40af39d2fcdb453aca8faac36, observed Windows bytes digest1eae0db2b0e3cad6a61b4867cfd60ebd21a2454c112c98445c1e9e0b4280cd75. This exactly equals its CRLF encoding; LF encoding equals catalog. Existing attributes cover top-level operations/*.md, not the new nested guidance or two new protocol JSON hash inputs. Both schema CRLF hashes also differ from their catalog LF hashes, so all three new hash inputs need explicit canonical checkout rules. No hash assertion, verification boundary or global Git configuration will be weakened.

Complete group FAIL; C1-C4 and DEF-049/050/051 stay held, new DEF-052 tracks cross-platform catalog bytes. Source review additionally identified an untested actual-native integration: the table holds its setup lock while the owner callback calls Discovery._current -> Setup._fresh and may reenter that same non-reentrant native lock. This is a hypothesis, not a proven defect. Next bounded diagnostic must exercise the real native WATCHDOG observe-to-table path with a synthetic provider; do not accept all-green counts as proof of that path.

All native/network/install scenarios were synthetic isolated CI/local fixtures, with actual filesystem/Qt adapters. No router procedure/private host/topology/path/credential or live runtime action was performed or published. Preserve initial failed runs and each source. Next: bounded clean-checkout/native positive-path diagnostic INTENT, then only proven smallest repairs and latest-source native/full platform requalification on this same PR.
