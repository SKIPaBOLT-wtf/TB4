# Scoped native owner-read and canonical checkout repair WIP

Step: RP-026. Attempt: A001. Checks: C1-C4 remain unaccepted.
Source: 6b1a4d19d5e4f349823b4367b5e19b4b7fe8a657. Pre-action INTENT RP-026-A001-0041 was published and read back at 4555699d19f96832f6a1a8ba47039dab379da594. This receipt records implementation, not qualification.

The exact four-file WIP is remotely published and verified. The new local-table module keeps the actual native setup lock, exact current revision/payload checks and the complete original current-owner callback immediately before the write. Only that callback receives a scoped read-only view of the actual held native port. Original native reads/binding checks remain; staging/promotion is refused; other threads use the original lock; escaped read ports expire; original store is restored in finally. Accepted Setup, Discovery policy and native drivers are unchanged.

Native regressions now include the actual Discovery.observe callback using protected setup/table storage with a synthetic provider, borrowed-write/stage/promote refusal, escaped read/binding refusal, other-thread lock contention, and owner refusal/exception preserving the exact pending UPDATE. Existing native permission/identity/restart/relocation cases remain. No test was executed in this edit unit.

Three explicit LF attributes cover the new nested guidance and two schema inputs. Original strict raw-byte catalog assertions and all catalog/schema/guidance bytes remain unchanged. Public contract documents the scoped reader without adding role authority or a takeover acknowledgement barrier.

Diff review: changes are confined to .gitattributes, the new local-table module, its native test file and the public contract. No private values, external request, provider adapter, router method, runtime permission repair or deployed change. The task's own local WIP commit 9c03387509636bd687d914dec0f7a2dd04da9084 is retained separately; public source SHA above is authoritative. A task-only input patch was rejected before mutation and then supplied as an ordinary context-checked update; this did not affect repository history.

DEF-049 through DEF-053 and all C1-C4 gates remain held until exact-source Windows/Linux/Qt/fresh-checkout and full hosted package requalification. Next: publish a fresh qualification INTENT, execute isolated native and new-checkout regressions, and run the existing PR35 hosted platform matrix; record real outcomes before acceptance.
