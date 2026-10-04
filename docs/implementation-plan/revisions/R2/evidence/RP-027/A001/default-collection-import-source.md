# RP-027 A001 — default collection import repair source

Intent RP-027-A001-0128; source `a71954afb45c9e667ae1dd554b6b134fcf7c17c9`; local retained `f46262c4407b0b7029fbe2ffacdcca1bfc8fa878`.

Exactly five authorized fixture/test paths and seven imports changed. Four reported modules now import tests.reconfiguration_support or tests.security.test_credential_contract. Nested root fixture and root/native evidence use tests.drive.test_native_docs_transport, allowing the root package's helper to resolve its actual drive dependency. Original fixtures and all assertions remain, no production code, protocol, default pytest configuration, helper PYTHONPATH or CI workflow change.

Entire source published/read back and exact diff checked. No tests ran in this source unit. Default collection and actual platform full/native/build qualification remain necessary; DEF074 OPEN, C1-C4 unaccepted.

Next: default full collection with PYTHONPATH removed rather than inherited custom helper directories, then native/full CI repeat on the repaired exact source.
