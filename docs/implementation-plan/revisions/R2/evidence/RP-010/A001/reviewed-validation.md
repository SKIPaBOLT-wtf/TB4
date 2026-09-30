# RP-010 A001 reviewed validation

Source: 179c76be7071692a36b4d6bfbecb02aee08dedbb.
Tested PR head: 1f9ce828e437f27022e27a7d18710a924ddce9da.
PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/18 .

## Invariants and compatibility

C1: Closed request/result/cancel/ACK and derived status schemas bind domain, target,
generation, deterministic operation ID, payload SHA256 and protocol 2.0. The result
digest covers binding/report/output descriptor. Compact leaves reconstruct binding
only from the same validated document snapshot. Mismatched generation, payload bytes,
descriptor, result content and ACK digest fail. Complete UTF-8/escaped entry budgets
remain within RP-009; oversized values fail without truncation.

C2: Malformed JSON/UTF-8, duplicate keys, nonfinite/boolean/noninteger fields, unknown
domain/target/version, identity/hash/timing faults and capacity/busy conditions cannot
reserve execution. Rejections bind ingress revision/generation/raw-byte hash without
reflecting raw input. Identical full-request repeats return existing status; changed
request with the same ID conflicts. Trusted restart state preserves duplicates.
Bounded history plus persistent target high-water generation rejects evicted old
requests instead of executing them. One busy target does not block another.

C3: Admission, claim/execution, publication and consumption remain independent.
Same-snapshot claim/expiry/withdrawal races admit one winner. After claim, timeout
becomes UNKNOWN, never NOT_EXECUTED. Cancel receipt/ACK/signal cannot prove
interruption; natural exit can produce DONE. Unpublished reports stay RETURNING.
Exact readback is required before terminal publication; reading does not ACK.
Only exact-result ACK allows recycle with retained history. WATCHDOG takeover has
no all-sink barrier; unknown old operations remain individually reserved.
Wait reasons, responsible roles, deadlines and next checks remain visible.

C4: Exported schemas/matrix and positive-negative fixtures agree with the executable
specification; 72 command tests qualify boundaries. Mapping preserves FETCH_BALL,
STOP_BALL, WAKE_BONE, DOG_PULSE and WATCHDOG concepts and marks new stages/encodings
UNRELEASED. Installed v1 state machine, schema and compatibility release catalog
remain unchanged. Role names assume later authorization/epoch enforcement; this
is not a deployed multiprocess engine.

## Final validation

Windows Python 3.11: python -X utf8 -m pytest tests/protocol
tests/security/test_ballpark_contract.py tests/feasibility tests/development
--basetemp=<new verified task-local directory> -ra: 472 passed in 17.53s, exit 0.
Exact 472 node IDs were collected with -o addopts='' --collect-only -q.
Code equality to the tested head was verified before the accepted local run.
UTF-8 ledger --base e42447f4fc0a1a42f398bfa6ff29048ebcce207d, public scanner and diff passed.
Linux CI 36784119389 job 110121290162: 1081 passed, 2 skipped in 16.86s.
Progress 36784119602 job 110121291594 passed ledger/history/security gates.

Desktop run 36784119423 at PR merge commit dcd8ab2c3dc505e57eb6f62e58d81fd7f2b9948c:
Linux job 110121290416: 67 GUI tests in 2.34s and 1091 full regressions in 17.59s.
Windows job 110121290649: 63 GUI tests, 4 POSIX-only skips in 2.89s.
Both WATCHDOG/FETCHER builds, bundle self-tests, GUI smoke and isolated
install/uninstall profile checks passed on both platforms.
Remote installer artifacts:
- tb4-desktop-Windows-dcd8ab2c3dc505e57eb6f62e58d81fd7f2b9948c: ID 11129661023, 119306625 bytes, sha256:1296c9acf00a1353374db9162a781da03647fc54c156b4562ea896a99056b320.
- tb4-desktop-Linux-dcd8ab2c3dc505e57eb6f62e58d81fd7f2b9948c: ID 11128619386, 312161107 bytes, sha256:78fd8fe347bd020187ebacff43d200ddb739df4dea450fa68ebcc9b5e903b38e.
Earlier native runs 36782991805 and 36783710218 also completed successfully;
they remain historical evidence and do not replace this exact final-source run.

## Preserved failures and DEF-012

The temporary exporter initially failed on an extra closing brace, fixed before
schema generation. The initial local ledger command included unsupported validate
(exit 2); the correct module/--base invocation subsequently passed. Initial 450
and intermediate 466 passing tests do not substitute for final source proof.
A transient Git fetch returned Empty reply from server. The wrapper continued on
old fetched head f27c3b88a755a4075fa73f04a644cb95b6b33a57 (466 passed in 18.17s);
this run is explicitly excluded. Remote identity, one checked fetch/fast-forward
and source equality preceded the accepted 472 run.

DEF-012: published STARTED 0006 self-referenced and its cursor omitted pending INTENT.
Original bytes are intact. Typed CORRECTION 0009 identifies actual earlier INTENT
0005 without changing execution facts or the failed outcome 0007. Guards reject
mismatched source/action/check/run, late or settled intents, outcome mutation,
duplicate patches and missing justification. Schema-first prepass preserves
allowlisted diagnostics for six malformed record classes. Existing ledger tests
plus 22 new correction/input cases pass (65 ledger tests total). Session publication
derives pending IDs and checks STARTED linkage before upload. Explicit A-001
amendment extends administrative recovery only; earlier accepted valid records
retain their meaning and immutable evidence. RP-010 acceptance stayed held.

## Limits, privacy and rollback

Synthetic specifications qualify design behavior. Production Doc CAS, artifact
transfer/bytes, owner epochs and authorization, trusted clock policy, corrupt-state
recovery, process cancellation/durability, GUI/helper wiring and release remain
later gates. Model restart state is trusted validated data. Unknown effects never
authorize automatic replay, including after WATCHDOG leadership changes.

All content is synthetic. No real profile, credential, root, network, workload,
role installation or live migration changed. Native installers use isolated runner
profiles; artifacts remain in CI, outside the <=100 MiB knowledge archive. Reverting
the draft cannot roll back live epochs/generations or delete unread/unknown work.
