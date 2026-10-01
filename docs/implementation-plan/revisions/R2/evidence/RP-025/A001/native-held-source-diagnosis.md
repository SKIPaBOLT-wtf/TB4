# RP-025/A001 — native held-source diagnosis (DEF-046)

Source: `6a9da65c39716052df61e4181741cb850d03379f`. Diagnostic INTENT: `RP-025-A001-0048`. Original hosted failure remains in [qualification failure](linux-held-key-qualification-failure.md).

Actual local Ubuntu WSL, Linux x86_64, CPython 3.12.3 ran the native adapter against bounded newly created synthetic private files on a supported native filesystem. No live TB4, external helper, owner credential or network configuration was used. Only closed booleans/counts were emitted; the task-owned files and their new directory were removed.

- Unforced probe: 256 rounds; equal metadata 0, held-recheck misses 0, original sealed content preserved 256. This did **not** establish natural timestamp coalescence as the cause of the hosted failure.
- Controlled timestamp observation: real descriptor identity, owner, permissions, ACL, mount, path-chain and seal checks remained active. Only observed timestamp tuple fields were held constant after changing actual synthetic bytes. Held recheck rejected: **false**; original sealed snapshot preserved: **true**; fresh-open content version changed: **true**. Diagnostic completed, exit 0.
- Source inspection: `HeldKey._recheck` compares the current source tuple with the admission tuple, then checks seals. It never compares the current source content to the admitted content version. The original introduced file at `a39427c4a104e0f61e3ea3231b1a06866848eefd` already contains that implementation. Later mount/zeroing changes preserve this gap. That is the proved originating RP-021 unit; the hosted filesystem's unmeasured timestamp behavior remains a hypothesis.

The sealed handle is immutable; this finding concerns the required pre-helper revocation check, not an alteration of the sealed copy. Preserve `test_original_mutation_cannot_change_already_admitted_snapshot` unchanged and add deterministic metadata/content, bounded read, zeroing and offset cases. The repair must compare actual source content using bounded mutable storage while retaining every existing native ownership/mount/path/seal check.

## Acceptance and recovery impact

The existing pure repair helper, called against the published manifest/registry for RP-021/A002, returns `REPAIR_CONCURRENT_WORK_REQUIRES_RECONCILIATION`: RP-025/A001 is IN_PROGRESS and never accepted. No state was changed by that diagnostic. This is its intended protection, not a helper defect.

RP-021 must reopen at A002; transitive accepted RP-022, RP-023 and RP-024 must preserve their A001 acceptance receipts and reopen at A002. Unaccepted RP-025 must retain A001/source/PR/full holds and be explicitly suspended with a settled journal. Add a narrow opt-in, schema-checked reconciliation of that unaccepted dependent, backed by matching published suspension INTENT/RECORDED OUTCOME; retain default concurrency rejection. No previous accepted checklist is silently replaced and no accepted RP-025 snapshot is fabricated.

Next: publish a bounded development-helper amendment/implementation INTENT; validate adversarial history/publication tests; explicitly suspend RP-025; publish coordinated RP-021 reopening before the native source repair. Full required CI and Linux/Windows native, Qt, frozen and installer gates must then be rerun on the actual repaired source.

## Completed Windows qualification from the same prior action

The existing Windows Desktop job `110554943487` in run `36917491747` completed successfully at test-merge checkout `d236ec143c924e8fad2ace657f6fd8acc4bbe49a`, source-identical to `6a9da65` for runtime/tests/SKILL/Desktop workflow. Real Qt: 71 passed, 4 platform skips; native Windows: 15 passed; protected stores: 30 passed, 4 Linux skips; loopback: 2 passed; BALLPARK: 75 passed; enrollment/profile: 79 passed. Full suite: 2232 passed, 81 skipped, 4 known strict xfails in 758.64s. Both package builds, frozen self/core checks, GUI/Setup GUI and profile-isolated install/uninstall passed.

Artifact `11190648979`: 120794727 bytes; SHA-256 `875e4106992f2976a33016890191a68646babda6beffdbae8506da1b81e5fa0f`. The raw log/artifact is not republished here. This success cannot accept RP-025 while Linux fails and does not qualify the forthcoming repaired source. No release or live deployment occurred.
