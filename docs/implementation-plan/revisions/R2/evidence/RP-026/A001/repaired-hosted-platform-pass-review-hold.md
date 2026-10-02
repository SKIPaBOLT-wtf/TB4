# Repaired-source hosted qualification, acceptance held for review

RP-026 / A001. Exact application source 6b1a4d19d5e4f349823b4367b5e19b4b7fe8a657. INTENT0045 qualification head e9e825be23a39e23c435b9e10076e302e330494e; actual CI, Progress and both Desktop checkouts 1cf964a40d2102bec0de52da22effd72be39cecd. Verified Git tree 7c0552a6ccef6f83c8d56a711e6ab839d2d48f75 is identical to the qualification head; parents are unchanged main33e7aeb1896df4709ee9cdca7134532bc536aeb5 and that head. Source-to-head changes are documentation/progress only.

| Run/job | Terminal result and actual checks |
|---|---|
| CI37025861081/job110900189553 | SUCCESS. Public scan; native Linux43, protected34, scoped loopback2; full2450passed27skipped4historical strict DEF-002 xfails in437.71s. |
| Progress37025861218/job110900190859 | SUCCESS. 235 development cases in12.30s, current/base-history/scan guards. |
| Desktop37025860808 Linux/job110900188119 | SUCCESS. Qt90passed4declared custom-dangling skips; native43/protected34/loopback2; BALLPARK75; enrollment79; full2473passed21skipped4historical strict xfails in359.55s. Both role builds and frozen self/GUI/setup/isolated install-uninstall/profile preservation PASS. |
| Desktop37025860808 Windows/job110900188477 | SUCCESS. Qt74passed20POSIX skips; native15/protected30passed4Linux skips/loopback2; BALLPARK75; enrollment79; full2387passed107platform skips4historical strict xfails in562.84s. Both role builds and frozen self/GUI/setup/isolated install-uninstall/profile preservation PASS. |

The real Linux Qt group has only four deliberate empty custom dangling-link skips, so denied-directory installer negatives executed as a non-root principal. New actual native table positive/read-only/escaped/thread/refusal cases are part of the full unfiltered suites; their existing win32/linux mark permits both hosted native environments. No new xfail masks a network-table regression. The four historical strict xfails are DEF-002 outside this changed scope; no runtime completion is inferred.

Published provider artifact metadata (read back, not downloaded/deployed/independently rehashed): Windows artifact11235622067,120812238bytes,digest sha256:76aec37349b821f34a51fc8e43285339d5bdc74edf69fd920d7345627bcae4e4; Linux artifact11235304282,314315368bytes,digest sha256:5ff8344a855c509a75dfa3b738337aa9cfb573ac8087ee33b919311f97ff0de3. Both names identify actual checkout1cf964a40d2102bec0de52da22effd72be39cecd and run37025860808.

Local exact-source 365-case native/Qt/source-gate results and fresh true/false autoCRLF/native positive reproduction PASS remain in repaired-windows-targeted-and-progress-milestone.md and native-owner-and-checkout-post-repair-pass.md. Earlier failures and hypotheses remain immutable.

Source review preserves installation/default/custom local storage, typed notices without private topology, optional stable-IP provenance and no new execution/enrollment/shared authority. Two remaining source-review hypotheses require bounded reproduction before acceptance: Discovery.status currently reads the table with allow_pending=True and may omit an already known pending table operation from its description problem; DescriptionAssistant.propose validates the supplied device against the current table but may not bind it to the device selected by begin. Neither is labeled a proved cause or passing invariant. A new diagnostic must check actual pending status and a two-device proposal, without changing source or a live system.

INTENT0045's actual local/hosted qualification is complete PASS, but C1-C4 and DEF-049 through DEF-053 remain held until this final review is resolved. No merge or live migration. Next: publish/read back synthetic native-pending and helper-target-binding diagnostic INTENT; retain actual results, then only a proven bounded repair and source requalification if needed.
