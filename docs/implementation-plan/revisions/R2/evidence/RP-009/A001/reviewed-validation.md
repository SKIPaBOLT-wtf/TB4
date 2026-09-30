# RP-009 A001 reviewed validation

Source: 25aecb2586f82525a1ca506ae50b5f532072ba6b.
Tested PR head: 3ebdc9daa121ca72cb9b6610cb7659fecfc4f154.
PR: https://github.com/SKIPaBOLT-wtf/TB4/pull/17 .

## Invariants reviewed

C1: One fixed native document owns control; deterministic indexed slots address ingress, leadership/forced request, catalogue, target work/result/cancel/ACK/status, history/quarantine and raw artifact descriptors. Status is read-only, cancel/ACK capacity is reserved outside the work queue. Business schemas/writer matrix remain RP-010; the structural validator does not authorize opaque bodies or execute work.

C2: One unconsumed work lane per target, with free ingress/work/result/artifacts/history required for new capacity. Busy/unknown/unread records are retained; one busy target does not hide another. Unknown slot IDs, extra dimensions, boolean/noninteger bounds, wraparound generations and free-with-content records fail closed. Record budgets count canonical UTF-8 and escaped JSON, not display characters. Capacity checks are pure observations, not reservations or shared CAS.

C3: Partial provisioning distinguishes explicit NOT_STARTED from UNKNOWN/CONFIRMED; missing receipts, duplicate physical identities or guessed path-shaped bindings fail. Unknown creation is inspected, never blindly repeated. Expansion adds empty indexed slots while preserving every old record and original input unchanged, including all retention classes. Shrink/no-op/revision wrap are rejected; actual authorized provisioning/content/access readback/CAS publication remain later RP-019.

C4: All 16 min/max dimension combinations and the setup defaults are validated, without real topology. Maximum saturated profile measured 514586 canonical bytes under 524288, with 694 logical records and 129 physical objects (one document + 128 reusable raw artifact slots), normal-operation creation count zero. Exact 378 collected test IDs are preserved. V1 tree/spec remain unchanged except a navigation link. DRAFT/UNRELEASED marker prevents mistaking this for a runtime protocol release.

## Validation

Windows Python 3.11: python -X utf8 -m pytest tests/protocol tests/security/test_ballpark_contract.py tests/feasibility tests/development --basetemp=<new verified task workspace directory> -ra: 378 passed in 17.76s, exit 0. UTF-8 ledger against ownership 1fadd483e99e538b8f24825f1d5c8439444f89dc, scanner and diff passed. No new local test failure.

Linux CI 36779824667 job 110106931301: 987 passed, 2 skipped in 11.39s. Progress 36779824707 job 110106933195 passed all ledger/history/security gates.

Desktop run https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36779824706 used PR merge build aa335c2862bf718e211df82491ddc408a14bddb8. Linux job 110106932421: GUI 67 passed in 1.31s; complete suite 997 passed in 10.26s. Windows job 110106932264: GUI 63 passed, 4 POSIX-specific skips in 2.51s. Both roles on both platforms passed bundled self-test, GUI launch and installer/uninstaller/profile-isolation checks.

Remote artifacts (retained in the CI run, not local archive):
- tb4-desktop-Linux-aa335c2862bf718e211df82491ddc408a14bddb8: ID 11127615490, 310741967 bytes, sha256:3198a26ffbfce9f5d1404e0e2ba982e5d79b34c2b69060cbd52ae75f34a81281.
- tb4-desktop-Windows-aa335c2862bf718e211df82491ddc408a14bddb8: ID 11126649626, 119088661 bytes, sha256:33bd3687eab1c771db066c59a9387da9fb1d6ab4af3030b99cba24e36e7f396e.

## Limits, privacy and rollback

This is a layout design and pure structural validator. It does not qualify throughput, all business-record fields, real provisioning, raw artifact publication, UI or same-host/multi-host provider operation. Existing BALLPARK inventory bounds do not imply enrolled execution capacity. Later schema fixtures must fit their assigned budgets or receive an explicit versioned capacity amendment; no truncated record may be accepted as complete.

Official provider references and current quota/size values appear in EXCHANGE_LAYOUT_CONTRACT.md. Product capacities and byte budget are explicit conservative design choices, not a quota increase or benchmark. Aggregate per-user/project request budgets and reserved control/heartbeat throughput are later RP-011/015/016 gates.

All identities and bodies are synthetic. No real object/root/profile/credential/service/network or installed app changed. CI artifacts remain remote, not in the <=100 MiB knowledge archive. Expansion only prepares a candidate; no rollback to older authority epochs/generations or deletion of unread/unknown records. Live migration still requires specific authorization.