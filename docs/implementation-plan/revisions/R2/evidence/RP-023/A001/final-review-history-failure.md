# Final local history precondition failed

Candidatebde76dba14bf205d06cf96268f0977742761995d, sourcea423b69e03bd43c756cfb1077a5920fed93b42de. INTENT0042; local session73924. Development196 passed14.31s; current ledger PASS22verified/sole pending0042; scanner0, complete branch diff0 and runtime/test/workflow/tools/protocol/config/packaging equality0. Main-base history returned1/EVIDENCE_IMMUTABLE.

Read-only Git name-status comparison against91d701fd481cc39c474bdd25adbff1c6f99e3a7e shows only newly added RP023 evidence, no modified/deleted historical evidence. The checker compares UTF-8 file text with `subprocess.run(...,text=True)` Git output lacking an explicit encoding. A Windows local default decoding mismatch is a hypothesis, not yet proven. Hosted Linux current/main-base history already passed. No final snapshot branch, ready transition or merge has occurred.

Next: inspect default Python/subprocess encoding and the first mismatching historical path; compare exact raw Git UTF-8 bytes to the same working file and immutable base. Do not normalize or rewrite historical evidence. If an environment-only cause is established, use the same explicit UTF-8 environment declared by hosted Windows qualification and re-run exact history validation.
