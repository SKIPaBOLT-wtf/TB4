# Fresh-checkout and actual native owner callback reproduction

INTENT: RP-026-A001-0039; run rp26-native-and-checkout-001, actual Windows CPython with native protected setup/table adapters.
Source: aba77c9aa9df314e3088dfb388a84a7f7011cb6a
Diagnostic checkout: 6bde01edd91a2fea4151ce4e2827356c27c56138
The bounded native/checkout diagnostic invariant exited 1; outer output cleanup exit is not qualification.

Two fresh public-only clones, empty task-owned hooks, exact source and command-local core.autocrlf settings. All seven catalog entry/profile raw digests match with autoCRLF false. With true, exactly these three new inputs differ, reproducing DEF-052 without a global config change:

| Public input | Expected LF / Git-blob SHA256 | Observed CRLF SHA256 |
| --- | --- | --- |
| skill/tb4/operations/device-description/SKILL.md | b7528e9003fe9b599845f4261f1760296773a2d40af39d2fcdb453aca8faac36 | 1eae0db2b0e3cad6a61b4867cfd60ebd21a2454c112c98445c1e9e0b4280cd75 |
| protocol/network-description-v1.schema.json | 366c5944df1eac692e0480d25190beb603ef644ea9210e387c1b9bc45545291c | 3ff7c642582bdc3ecaac292b89e09e5c5d8fb4281c72e9ac263fdbe876c0bda2 |
| protocol/network-table-v1.schema.json | f90e4b2ea1d44c24d8c51d01822e66638ff837a835c9988be25e02e374cd55b0 | 1d421a8daee28e5a532d21ba6df8d889293ec997efc758729770adb8bf34446d |

Actual native positive path: use the existing build(store=native_settings(...)) synthetic commissioned provider/leadership/clock fixture; configure a real protected native table, then unmodified Discovery.observe for one synthetic observation. Discovery returned OBSERVED and durable catalogue used1; native table used0. Same exact UPDATE remains pending with requires_owner true, ordinary table read reports NETWORK_TABLE_INSPECT_REQUIRED. Current-owner checks were PASS, PASS, SETTINGS_BUSY. Instrumentation only captured/rethrew closed codes, with no changed decision or suppressed failure.

Source/trace establishes new DEF-053: LocalNetworkTable holds the real setup lock while invoking current_owner; Discovery._current calls _local -> Setup._fresh -> PrivateSettings.read and attempts the same non-reentrant native lock. Native locking correctly refuses. Memory fixture locks did not reproduce that integration; previous target/native-table standalone tests did not exercise the actual discoverer callback. Accepted native/discovery policy is not proven defective and stays unchanged.

Required smallest repair: retain the actual setup lock/snapshot/fresh native binding and refresh the existing full owner callback through a scoped read-only view of that held port, without a second lock acquisition. Other threads and escaped readers must not borrow it; writes through it must refuse. Do not skip owner refresh or weaken native locking/hash checks. Add real native positive integration, read-only/expired context negatives and existing owner supersession/restart regressions. Separately add explicit LF checkout attributes for the three new hash inputs, preserving all catalog/schema/assertion bytes.

All native payload/paths/principals/root bindings and raw fixtures remain protected task-owned data; no actual provider/network/user installation/credential was accessed. Pending fixture operation is retained and not replayed. All C1-C4 and DEF-049/050/051/052/053 remain held until exact repaired native/Qt/fresh-checkout/full packaged requalification.
