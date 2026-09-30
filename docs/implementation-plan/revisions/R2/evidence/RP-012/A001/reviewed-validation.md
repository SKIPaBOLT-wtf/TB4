# RP-012 A001 reviewed security/failure gate

Source: f57c88138e35130379b9a040714836ac8de702a3.
Test head: 3f106d92e8441c9602cd4e396b5b7df8ebec2762.
Current progress correction: 68ad0e3872e1abd300037c6514f294d45ce94ffa.
The implementation/tests/protocol/package scope is equal between final test head and current progress. Initial source d31bfe687bda0944307ca82f279d2a2296c4bacc remains in history.

This accepts the design artifact, not deployed security or a released runtime.
No real ACL, credential, local service, network, instruction installation or authority migration occurred.

## Invariant review
C1: closed 23-action role map, 10 distinct actor roles, required trusted predicates,
unknown/right-confusion rejection, immutable operation/target/payload/media binding.
Each action is exercised under every actor and with each required predicate removed.
Co-location never merges roles. Predicate booleans never become runtime grants.
One native document has principal ACL, not field-level authorization: malicious
unrestricted editors are explicitly outside the cooperative failover model.

C2: 21 closed fault reasons distinguish operation, target, transport, capability,
coordinator and domain response. All preserve evidence, disallow automatic replay
or clear and never wait for all sinks before owner takeover. Unknown work remains
individually reserved. Target credential loss differs from authority credential loss.
Cancellation request is not interruption proof; unavailable storage does not stop
local supervision or grant a new root.

C3: 512 KiB UTF-8 object parser rejects duplicate keys, nonfinite/exponent overflow,
invalid encodings, 32-depth/50,000-node excess and malformed roots. Exact artifact
slot/enrolled binding, complete bytes/hash, 8 MiB cap, fixed interpreter/suffix and
derived basename reject foreign URLs/paths/commands. Result is untrusted data, not
instruction/authorization or a secret-free guarantee. Runtime streaming/no-follow
temp files, actual ACLs, capture completeness, bounded drain, burst/rate fairness,
log redaction/rotation and instruction/result separation are mandatory named future
qualification, not claimed by this pure model.

C4: all 4,608 backend/platform/topology/launcher/session/trust/wake/network mode
combinations have explicit unsupported reasons and required missing evidence gates.
Supplying every gate name still yields no runtime/release authorization. The
amendment binds RP-059/060/061/064 to consume the mandatory evidence inventory;
essential product requirements cannot silently become optional. Installed v1
behavior and previous accepted gate meaning remain unchanged.

## Validation
Windows Python 3.11 isolated process environment, explicitly verified child Python
resolver and inherited UTF-8. Same 987-node scope:
python -X utf8 -m pytest tests/protocol tests/security tests/development tests/feasibility tests/fetcher tests/drive tests/coach/test_instruction_selection.py tests/integration/test_google_transactions.py --basetemp <new-task-local-directory> -ra
985 passed, 2 skipped in 28.46 seconds, exit 0.
Skips: tests/fetcher/test_cancellation.py:258 SIGTERM-ignore POSIX behavior;
tests/drive/test_google_client.py:122 POSIX mode assertion, not Windows ACL proof.
109 new security cases include the all-combination matrix and per-predicate loops.
Exact node IDs: local-collected-nodes.txt (987 collected in 0.39 seconds).

UTF-8 ledger --base 0423195ac49a9be78f693476cb0a7fb77ba0e83d:
PASS, 64 steps, 11 already verified, sole pending validation INTENT 0013.
Public scanner clean; diff check and source equality exit 0.
Linux CI 36789476451, job 110138712535: 1259 passed, 2 skipped in 15.68s.
Corrected Progress 36789716143, job 110139492475: all steps success.
Current same-source Linux CI 36789716197/job110139492537: 1259 passed, 2 skipped in 17.42s.
Native Desktop 36789716131, synthetic merge 998eaa5c17a62f46f2999fe6af3a87f04f798ebc:
- Linux job110139492660: GUI 67 passed in 2.52s; full suite 1269 passed in 13.67s.
- Windows job110139492401: GUI 63 passed, 4 platform skips in 4.07s.
- Both jobs built WATCHDOG/FETCHER and reported PASS for each bundle self-test,
  real GUI smoke, install/uninstall and profile isolation.
- Earlier Desktop runs 36789123653 and 36789476376 also completed successfully;
  they are retained history, not replacements for final fixture/progress checks.
Artifact API metadata (provider-reported archive digests, no local download/rehash):
- tb4-desktop-Linux-998eaa5c17a62f46f2999fe6af3a87f04f798ebc; ID 11131930946; 312198495 bytes; sha256:5845e58ee417a52a561ad079ad2820ecb6ef96d0d4ff27495e4744f64a28feb5
- tb4-desktop-Windows-998eaa5c17a62f46f2999fe6af3a87f04f798ebc; ID 11131136893; 119322678 bytes; sha256:63f1485d7c09d93fac28d6190707ca09a3680ad9a05c467d3cf8ce2cc3acc31e
No required workflow remains running.

## Retained failures and repairs
DEF-014: initial Windows run had 984 passed, 2 skipped, 2 errors in 27.72s.
The two errors are setup/teardown of one node, not two collected tests; the
earlier journal total 988 was explicitly corrected to collection 987.
A bounded diagnostic reproduced 16 passed/92 deselected/2 errors in 0.33s:
pytest exports raw node ID through PYTEST_CURRENT_TEST, exceeding Windows'
32767-character environment-variable limit. Added descriptive bounded IDs to
17 hostile parser cases; input bytes and rejection assertions unchanged.
The original diagnostic was tool-truncated; exact proof came from the separate
compact diagnostic, never invented from that truncated output.

A subsequent local pytest returned exit 0 but its buffered shell output was lost
when a later ledger guard threw. That run is not used for exact count/duration.
Progress 36789476484/job110138712451 independently failed LEDGER_INPUT_INVALID;
typed validation proved REPAIR_HOLD_REMOVED: a session projection had put DEF-014
instead of RP-012.C1-C4 into revalidation_required. Corrected current projection,
retained all original events and untested/supported hypotheses, changed no validator.
The canonical cursor uses known_open_defects, not extra session-only fields.
Output now persists before later guards; final complete retained Windows results
above supply the missing evidence.

## Privacy, compatibility, rollback and limits
Only synthetic UUIDs, payloads and example.invalid references. No deployment facts
or secret values. Public source/diff/scanner review passed. Existing v1 runtime,
provider behavior and native credential stores are unchanged.
Rollback removes unreleased specification integration only; never broadens authority,
replays unknown work or selects a different backend silently.
Native package regressions are packaging compatibility evidence, not live R2
authentication, field ACL, hostile-code sandbox, actual topology or ownership
qualification. All real gates in r2-security-matrix.json remain NOT_QUALIFIED by
RP-012; scoped later acceptance and owner-authorized live testing remain required.
