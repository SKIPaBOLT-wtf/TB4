# Pending notice and exact description context repair WIP

RP-026/A001. INTENT0051 was published/read back at4751afd6415f0b66133c42e5d272f69386f80634. Exact five-file source 2575de12ffed36a2e3e739710a9183dd0bfa437d is published/read back; the task's local source commit4c3cb62e808fa46bfe04b67a32abf3a207caf2d7 remains separately preserved. This is an implementation receipt, not qualification.

Discovery.status now reports a known pending local-table operation as NETWORK_TABLE_INSPECT_REQUIRED. It retains the valid table and observation evidence; status never clears or retries the transaction. Only the new reporting branch changed; original Discovery._current, native locks, capability/current-owner checks and table transactions remain identical.

DescriptionAssistant.begin clears partial/old context first and publishes a new compatible pin plus exact device/revision only after the full schema/draft succeeds. Propose must use that exact identity/revision and a still-current table/pin; failed proposals clear their earlier candidate. Successful confirmation ends that proposal context and requires another begin for a later revision. It still updates only the owner-approved local table and confers no enrollment/execution/shared-authority grant.

Six concrete new regression cases were added: actual protected native pending notice without replay, two distinct existing device targets, silent revision rebase refusal, failed begin, invalid new proposal after a valid candidate, and successful approval requiring fresh begin. Existing tests/invariants are retained. Public contract clarifies both boundaries. Guidance/schema/catalog/attribute bytes and UNRELEASED status are unchanged.

One attempted patch had an unmatched documentation context and was rejected atomically before repository mutation; clean status was inspected, then the correct context applied. No test/build was executed in this edit unit. Diff review confirms the exact bounded five-file scope and no private fixture values, native bindings, real topology or router/provider procedure.

DEF-049 through DEF-055 and C1-C4 remain held. Next: publish a fresh exact-source qualification INTENT, reproduce the same boundaries in new fixtures, run targeted/native/Qt/source guards and the existing PR35 hosted full platform/build/distribution matrix. Earlier failures, successful runs and hypotheses remain immutable.
