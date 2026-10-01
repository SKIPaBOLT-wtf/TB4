# RP-016 A002 progress repair and revalidation

Product leadership source remains dfa260eae0675db46a2c56424cc4b5adbf348400. Repair source bde4f0f4eeec21594574b80c884b06202d55f44f; test head 80a0beac155b2b5943cdea2a7451139971e25b4a; PR25. The original A001 evidence remains immutable and is retained in manifest acceptance_history.

## DEF-017 and actual correction
Post-merge f3cc8b1447c8ab176694529169b40689d5eaf81a inserted unsupported repair_holds and missed the global linked checkbox. Main Progress36797925029/job110165519543 and36797996091 failed; the local ledger returned RECORD_SCHEMA_INVALID. The checkbox was corrected, then the invalid field removed under A002, retaining its exact record in invalid-step-record.json.
Next validation: existing101 development tests passed in11.35s, scanner/diff/source identity passed, but ledger returned INTENT_PHASE_INVALID (Progress36798199292). A0010010 and A0020001 had prior diagnostic facts in INTENT observed. Static validation identified this independent metadata error; no product failure was inferred.
The repair adds a closed optional intent_note_correction. A later CORRECTION retains the exact original observed text, references the earlier PENDING INTENT, has no simultaneous reference correction, matches source/action/check/item/attempt, and permits only one null relocation. Original stored events and actual outcomes are untouched. No new intent, permission, execution outcome or cleared pending state is inferred. A0010012/A0020008 retain the original notes. New publisher preflight also refuses non-null INTENT observed before publication.
24 new cases cover exact preservation/pending state, FAIL/UNKNOWN retention, source reachability, wrong old/new text, changed field, unknown property, absent note/target, wrong event/outcome, cross-action/check/source/identity, duplicate and reversed correction. Original tests still reject an uncorrected malformed INTENT.

## Reacceptance against all four original invariants
C1: the exact acquisition/renewal implementation and persisted owner/epoch/readback rules from A001 are unchanged; leadership regressions pass again.
C2: owner/epoch/exact revision fences and resumed-old-owner/force-request checks are unchanged and passing. Previously admitted external effects remain uncertain.
C3: all63 concurrent-start/clock/partition/restart/force cases are in the passing selected suite. No native OS or provider condition was newly simulated as a real environment.
C4: stale or forced takeover goes directly ACTIVE without any old-host/sink acknowledgement. The suspension counterexample remains passing. Documentation failure has no contrary runtime evidence.

## Execution evidence
Windows isolated Python3.11, process-local venv PATH/PYTHONUTF8=1/PYTHONPATH=src:
python -X utf8 -m pytest tests/drive tests/fetcher tests/feasibility tests/protocol tests/development tests/integration/test_cancellation_race_reproduction.py tests/integration/test_result_publication_reproduction.py tests/integration/test_google_transactions.py --basetemp <fresh-task-temp> -ra
1105 passed,2 skipped,4 xfailed in26.38s, exit0;1111 exact nodes collected in0.51s. Two POSIX-specific skips and four known DEF-002 cancellation expected failures unchanged.
CI36798634495/job110167734406, merge5678ce4 of test head into ba3e50e57bfc20d9272bddd22f58dc3585eed50a:1522 passed,2 skipped,4 xfailed in21.34s, success.
Progress36798634580/job110167734665: all schema, history, development regressions and public-data checks PASS.
Local ledger on A002 branch base and accepted-repair base88e76169 PASS; scanner clean, diff-check0. Product src/protocol/workflow/packaging/skill equality against A001 test head4e0eac60 exit0. Therefore original Windows/Linux package evidence is reused without a redundant build; tools/tests/docs are the only source changes.

## Scope and rollback
No deployed code, native document, device, credential or network action. DEF-001/002 remain open; no full-runtime qualification claimed. Rollback of the parser must not discard correction history; retain compatible append-only parser while restoring product source. All failed commits and original evidence remain available.