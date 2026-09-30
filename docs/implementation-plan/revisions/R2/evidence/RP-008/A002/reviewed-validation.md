# RP-008 A002 reviewed design acceptance

Source correction: `f576f0815669af5708f238c1fb34d7e3942ef70a`; design/model source: `27fd1e2aa149a9df7ee57c29febfc5c0a9b1d862`.
Tested PR head: `b43d6afeb0ab6eafd13a90eeb912a355d0a0edcc`.
PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/16 .
Owner decision: RP-008-A001-0016; current amendment:
`docs/implementation-plan/revisions/R2/amendments/RP-008/A-001-native-docs-authority.md`.

## Accepted invariants

- C1: A001 actual raw Drive/Docs connector inventory remains unchanged. Raw precheck/write is rejected for exclusion; Docs strict requiredRevisionId was verified on one isolated fixture with stale rejection/fresh success and verified deletion. One native document holds authoritative control; artifacts are bounded raw bytes referenced by committed identity/hash, not alternate authority.
- C2: 24 additional model cases and the original 17 counterexample/candidate cases cover contender permutations, incumbent progress, delayed/partitioned observations, uncertain clocks, old process suspension, wrong epochs/domains, interrupted activation, lost replies, all required sink receipts, incomplete/unknown effects and durable operation deduplication.
- C3: Owner-authorized commissioning binds one exact authority/domain; no guessed same-name adoption. Incumbent preference uses observed progress, not age. Epoch CAS arbitrates; new owner remains ACTIVATING until every enrolled effect gate advances its durable floor and drains older effects. It cannot declare ACTIVE using a partial barrier.
- C4: Select the owner-approved native Docs strict-CAS authority plus mandatory enrolled durable effect gateways as the Google-mode design. The proof obligation explicitly includes authenticated exclusive mediation, persistent epoch integrity and known completion/containment of older effects. The model proves ordering safety under those assumptions; later implementation and actual adapter/gateway qualification remain mandatory. No raw Drive-only lease, timestamp-only election, optional barrier or disabled-takeover substitute is accepted.

The most important schedule is an old effect arriving after authority CAS but before its sink fence: it can be admitted only during ACTIVATING and must drain before the new ACTIVE. After all fences/activation, old admission is rejected. This is a precise distributed cutover boundary, not instantaneous remote revocation.

## Executed validation

Windows Python 3.11: `python -m pytest tests/feasibility tests/drive tests/development tests/coach/test_instruction_selection.py --basetemp=<new isolated work directory> -ra`: **298 passed, 1 skipped**, 12.82 s, explicit exit 0. The skip is POSIX mode-bit assertion; Windows ACL qualification remains RP-020. Source/tools/tests/protocol/packaging/skill bytes match both the original test head and final repaired head; only progress/evidence documentation changed.

Linux full CI [36776799750](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36776799750), job 110096644489: **902 passed, 2 skipped**, 16.02 s. Linux Progress [36776799850](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36776799850), job 110096642657: all tests, ledger, preserved history and public scan passed. No production/protocol/packaging/SKILL change; no Desktop rebuild needed.

Windows history check: `python -X utf8 -m tools.development.ledger --base b41faf1540d7fbbb8b173a0d284bf0563a68a578`: exit 0. Public scan and diff check exit 0. Exact collected node IDs are in `collected-tests.txt` (299 items).

## Preserved failures and operational details

Initial Windows assertions completed but pytest session teardown failed on access to the shared temporary current link. A newly verified nonexistent workspace basetemp avoided that shared cleanup; no existing temporary directories were deleted. An initial direct-file ledger invocation failed a package-relative import; use `-m tools.development.ledger`.

Initial Progress 36776444553/job 110095444565 correctly rejected a new banner inserted into immutable A001 evidence (DEF-011). The repair restored exact original bytes; current status belongs in README/amendment/journal. Initial Linux CI 36776444600/job 110095452490 had already passed 902/2 in 16.06 s. Preserve both results.

Windows default locale decoded a UTF-8 em dash in Git stdout differently from the UTF-8 evidence file, producing a false EVIDENCE_IMMUTABLE even after byte restoration. Exact raw Git/worktree comparison proved equality; `-X utf8` passed without changing the validator. Use UTF-8 Python mode for ledger/checkpoint commands on this host. This is a known invocation precondition; locale-independent default decoding is not claimed.

A fast-forward refused the locally restored owned evidence file. Synchronization used a non-destructive mixed reset followed by restoring only known published progress files. Tested code was unchanged. No user changes were discarded. The preliminary source case count 25 was corrected to the collected **24**.

## Limits, privacy, compatibility and rollback

No actual gateway, restart durability, authentication, remote process containment, router/SSH/WOL effect sink, shared-folder adapter, throughput or multi-host pilot is qualified here. Real fallback/release acceptance still requires RP-015/016/017/018 and later negative/live gates. Authority partition or ambiguous old effects can hold activation; hiding that limitation would invalidate the design.

Synthetic identities only. A001 private fixture identity/revisions are omitted and the fixture is already removed. No live root, profile, credential, service, network or installed instruction was changed. Historical v1 evidence stays immutable; EC-12's new interpretation and affected future-step bindings are explicit amendments. No mixed v1/v2 writers or silent migration. Never lower epochs or restore old authority snapshots for rollback; retain unresolved operation evidence.