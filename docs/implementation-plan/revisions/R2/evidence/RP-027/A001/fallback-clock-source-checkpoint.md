# RP-027 A001 fallback clock fixture-only source

Source 7d571ea43040aeb0b1eae2fff3853387093c1242; verified INTENT RP-027-A001-0031 atddffdfae5c6a61451cd3a27613e3376f04ac5ba7. Exactly tests/drive/test_reconfiguration_effects.py changed. Local source commit 663cdbdb084733db7a7c7636fe7485f2372c3284 retained on its own preservation branch.

The test helper reads the actual synthetic incumbent heartbeat and derives ceil(heartbeat + current configured lease_stale_s). The same sample is passed to acquire and adopter context. Production default stale120, fresh owner guard, role acquisition/renewal, UNKNOWN preservation and all683 predicate assertions remain unchanged. Failed source/artifacts and actual INCUMBENT_FRESH result remain preserved. No live clock/effect/authority/profile was modified.

Static diff/privacy/rollback checks passed; source readback verified. No tests/application imports/build in this unit. DEF-059 and all C1-C4 holds remain open. Next: separately verified exact24-target repeat in newly owned absent fixture data; no success inferred from source correction.
