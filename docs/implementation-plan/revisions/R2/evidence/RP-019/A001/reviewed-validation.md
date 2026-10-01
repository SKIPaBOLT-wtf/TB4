# RP-019 A001 reviewed validation

Final implementation source: `11e65c3a5d70e5a8ab8c264cf4d2477126642ef4`.
Product seed correction: `97c7868e6682abbeeea0b58ddd57cd29d9e5f2bd`.
PR28: https://github.com/SKIPaBOLT-wtf/TB4/pull/28 .
Ownership base: `363b9a1faec2f7645c8afa119374e0136a0a60ac`.

## Invariants reviewed

C1: seed_document uses the reviewed RP009 capacity/layout for all logical records.
One native authority and exactly two bounded raw objects per target are allocated.
Initial leadership and force records share acquisition generation 1. Native Drive
creation carries root/domain/setup/slot/operation properties in the same request;
folder initialization is exclusive, server-local and identity checked.
Maximum/minimum/default capacities are exercised. STORAGE_READY is only storage
readiness; real descriptor and enrollment remain explicitly unconfigured.

C2: bootstrap saves seed/UNKNOWN before creation, pins document/tab or physical
folder authority identity and confirms seed by canonical readback. Commissioner
saves exact CAS intent privately and shared UNKNOWN before one live create.
Recovered pending writes and lost create/seed replies use inspection only.
Repeated setup preserves IDs, payload bytes and file identities. Changed root,
capacity, operation, size, metadata or file identity refuses instead of resetting.
A missing ambiguous creation remains incomplete; no cleanup/replay is inferred.

C3: standby cannot allocate. A stale successor wins RP016 CAS without sink
acknowledgements and inspects the same prior allocation; the old owner cannot
publish after supersession. An injected takeover before old-owner CAS prevents
old creation. Existing unread capacity blocks new admission and is retained.
Private checkpoint tests prove cross-process locking, atomic replacement failure,
staging recovery, corruption/binding/digest/size/hardlink/protection refusal.

C4: repeated native/folder setup and ordinary native lease renewal retain the
same physical inventory and forbid new creation. Normal READ/CAS ports expose no
allocation/delete operation. Strict development metadata correction is confined
to malformed nonterminal STARTED metadata, with unchanged original bytes, exact
run text/source/action identity and negative cases preventing invented success.

## Retained failures and correction scope

Initial source `78e4f580af1d412fdb7e3dea9ccb345ca36a0564`: 22 failed,
25 passed,11 Linux-only skipped/1.74s/exit1 (FORCE_GENERATION, DEF022).
The earlier lost output receipt is explicitly unknown; it is not a pass.

DEF023 preserves malformed event0013 (RUNNING, absent run_id), initial Progress
failure36808345887/job110197613822 and later incomplete repair registration
failure36808840595/job110199126600. Correction0017 and complete C1-C4 repair
holds restore strict validation without changing history or actual results.

## Confirmed receipts

Windows focused product:47 passed,11 Linux-only skipped/500.18s/exit0.
Windows development:146 passed/11.57s/exit0.
Collection:1718 exact nodes/.66s/exit0 (two missing-PySide modules excluded).
Corrected product Linux CI36808345826/job110197613690:
1693 passed,2 skipped,4 retained DEF002 xfails/406.44s.
Final source Linux CI36808840543/job110199126432:
1714 passed,2 skipped,4 retained DEF002 xfails/378.36s.
Required SSH and all11 new actual folder tests ran in Linux CI.

Exact-tree progress validation: current snapshot809216f231a19f37443995168fb376516e98faa3
and validation commitdbc81e95f772931700a604a853c9d1b4edfff6f6 share tree
0addb6f5c4673379d5ac7e5d78eece9033d75537.
Progress36809391907/job110200828285 passed146 development tests/5.19s,
real ledger, append-only history and public scanner. Local ledger/history,
scanner and diff also passed after complete repair registration.

## Scope and rollback

No real Google object, protected home exchange, installed profile, credential,
network or deployment was changed. Google tests exercise actual adapter request
construction against a synthetic atomic service; existing RP008 real CAS proof
is a separate prior gate. Linux tests create new isolated ext4 fixtures; no
physical power loss, xfs hardware or real remote provisioning qualification.
Private journal ACL verifier and provider transport credentials/wire bounds are
injected qualified ports; actual Windows/Linux store qualification follows RP020/021.

Interrupted setup remains UNKNOWN/PREPARING, with exact identifiers retained.
No automatic deletion/reset/migration. Removing even an unreferenced live object
requires separately authorized scope. Previously admitted external effects can
finish after takeover; this does not block election or authorize unknown-job replay.

## Final full platform and package receipts

Windows local full:1675 passed,41 skipped,4 retained strict DEF002 xfails/536.97s/exit0. Of41 skips:33 Linux server/folder/SSH,6 other POSIX and2 unavailable GUI modules; exact collected nodes are in collected-tests.txt.

[Final Desktop36808840561](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36808840561): Linuxjob110199127084 GUI68/1.70s and full1725+4xfail/596.11s; Windowsjob110199126714 GUI64+4skip/2.70s and full1686+39skip4xfail/698.92s. Both roles built and passed bundle_self_test, gui_smoke and install_uninstall_profile_isolation on each OS. Checkout merge25511f02152acbefdcfe8d243a8e73b112b0d82e has exact implementation/protocol/tests/tools/workflows/packaging/config/skill equality with final source11e65c3.

Provider-reported artifact metadata (not downloaded or independently rehashed):
- Windows11139167062,120704700 bytes, SHA256 0a7c32c1299987b54c11dd4ae241b8af6a4a47940f0b746a484a44a838daff64.
- Linux11138937190,314172986 bytes, SHA256 18fcfe0ae1a4789013a4e32d2e8bb3e59160b42a723bf3d680f410be125338f7.

All required native tests and package jobs completed; no running/unknown operation remains. Source/privacy/compatibility/rollback review found no installed migration or public sensitive data. Earlier failed sources and gates remain in first-validation.md, progress-failure.md and intermediate-validation.md; DEF022/023 close only with final VERIFIED acceptance.
