# RP-026 final exact-source hosted qualification

Application source 2575de12ffed36a2e3e739710a9183dd0bfa437d; qualification head 532a81fdef7cef012d1ed842938941ff4a3f8cb3; actual four hosted job checkouts 1f113f8f6b1826ab211f2ab7622f9a6ecb24aab7. Git tree bb7e51729dac8520603171d160d76fc679cfc3d1 is identical to qualification head; verified parents are unchanged main33e7aeb1896df4709ee9cdca7134532bc536aeb5 and that head. Subsequent branch differences are documentation/progress only.

| Run/job | Actual terminal qualification |
|---|---|
| CI37030150351/job110914647567 | SUCCESS: scan; native Linux43/protected34/loopback2; complete2456passed27skipped4unchanged strict DEF-002 xfails in662.20s. |
| Progress37030150738/job110914649141 | SUCCESS:235development cases in6.81s and current/base-history/public guards. |
| Desktop37030150369/Linux job110914647852 | SUCCESS:Qt90passed4declared empty-custom-link skips; native43/protected34/loopback2; BALLPARK75/enrollment79; complete2479passed21skipped4historical strict xfails in584.58s; both role builds and actual frozen self/GUI/setup/isolated install-uninstall/profile isolation PASS. |
| Desktop37030150369/Windows job110914647439 | SUCCESS:Qt74passed20POSIX skips; native15/protected30passed4Linux skips/loopback2; BALLPARK75/enrollment79; complete2393passed107declared platform skips4historical strict xfails in772.36s; both role builds and actual frozen self/GUI/setup/isolated install-uninstall/profile isolation PASS. |

Current native table and helper context tests are in the full unfiltered suites. Linux Qt's only4skips are deliberate empty custom dangling-link cases; actual non-root denied-directory installer cases passed. Windows platform-skipped Linux cases are covered by the real Linux job. Four historical strict expected failures remain tied to DEF-002 outside this source change; no new xfail was introduced or called a pass.

Provider artifact metadata read back, without download, deployment or independent archive rehash:

- tb4-desktop-Windows-1f113f8f6b1826ab211f2ab7622f9a6ecb24aab7: id11238565148, 120823192bytes, sha256:9c2a8cb54c6a3c33fdaed2a52b104ae2b616e478acbe95b75485b9b85e664feb, qualification head532a81fdef7cef012d1ed842938941ff4a3f8cb3.
- tb4-desktop-Linux-1f113f8f6b1826ab211f2ab7622f9a6ecb24aab7: id11237378944, 314335154bytes, sha256:c6e21c79973932af54f52615e997ba0d03277f7dbfb6639cfb8e9c041592c2f7, qualification head532a81fdef7cef012d1ed842938941ff4a3f8cb3.

Local371case closed status receipt, exact source gates and actual native/two-device diagnostic are retained in complete-context-windows-and-progress-milestone.md, complete-context-windows-case-status.json and context-boundary-post-repair-pass.md. Both real-native default/custom/restart/permission/conflict/owner/refusal and isolated packaged profile boundaries are reviewed. This is actual hosted Windows/Linux x64 plus synthetic commissioned provider/topology/clock/peer faults, not live provider/real-home/ARM64/XFS/ReFS/physical power-loss or release qualification. UNRELEASED remains authoritative. No real system/network/credential/table was deployed or migrated.
