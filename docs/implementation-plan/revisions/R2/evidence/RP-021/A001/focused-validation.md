# RP-021 A001 repaired focused qualification

Source16e403e7b76b1e9bc2e4e8946d140ddb8778db3c; Windows Python3.11.
Five RP006/Windows/Linux credential modules in a fresh synthetic test root:
156 passed,33 actual-Linux-only skips in0.33s, exit0. Passing total includes
RP00621, Windows50 portable+15 actual native, Linux70 portable/parser cases.
The33 Linux kernel tests require actual hosted Linux, not simulated acceptance.
Original failed source/run remains in first-validation.md (DEF027/028).

Full collection1912 nodes in0.72s, exit0; exact names in collected-tests.txt.
Ledger with ownership base415008b180cb2c0b97bdff40c8e21a066d6dc6b1:
20 verified, only pending focused INTENT0007; exit0.
Public scanner clean and base-to-head diff check exit0.
No source failures remain in this scope; native Linux, complete platform
regressions and installer acceptance are not yet observed.

DEF027 bounded IDs retain empty/65537-byte values and rejection assertions.
DEF028 pure parser18 cases verify ext4/XFS agreement and reject ext2/ext3,
unknown/mismatched magic, missing/duplicate/malformed/oversized kernel tables.
No mount operation, key/ACL edit outside fresh fixtures or live deployment.
