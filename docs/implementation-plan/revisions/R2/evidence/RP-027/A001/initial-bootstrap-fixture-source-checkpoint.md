# RP-027 A001 initial bootstrap fixture-only checkpoint

Exact source 95ee0e15cf467af4bbeb8b13a8c4d1868d135db3; verified repair INTENT RP-027-A001-0027 at2b91f5f9da820b60712ec715bb7ffdcb878a4a6e. Local source commit 397cb673443c6d7ddededa7ee689c0fd82256182 remains on its owned preservation branch. Only tests/drive/reconfiguration_effects_support.py and tests/security/test_reconfiguration_effects_native.py changed.

The new test-only factory chooses the controlled synthetic original bootstrap identity before the first native profile write, then uses existing actual Bootstrap/NativeCommissioning/Commissioner and freshly verified initial_grant. Existing discovery and descriptor adapters populate the one initial authority; no old authority/election/generation/profile is reset, copied or rewound. Accepted ready/build compatibility factory and all production guards are unchanged. A new native predicate checks original initial acquisition, epoch1, single Docs authority and untouched target-work generation. Native protection negative expects exact NATIVE_CHECKPOINT_INSPECT_REQUIRED, retaining refusal/no-mutation checks.

All original682 predicates are retained; a new actual-bootstrap predicate is added. Earlier failed fixture frames/reports and hypothesis chronology remain untouched. Code/pins/contracts unchanged. Static diff/privacy/rollback review passed; no tests or application imports occurred. DEF-058 stays OPEN until actual repeat and full mandatoryC1-C4 rechecks.

Next: separately verified fresh owned-fixture exact24-target repeat, actual exit/names/failures/skips; no result is inferred from source editing.
