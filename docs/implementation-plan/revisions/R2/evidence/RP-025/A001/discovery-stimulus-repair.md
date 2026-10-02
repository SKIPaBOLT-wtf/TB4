# RP-025 approved discovery stimulus repair

Source `86d4d32598616b935a7b8b2623d0c3a28e65767d`; authorized by `RP-025-A001-0017`. Only the new test module changed. The refresh test now builds a new synthetic authority/fixture with ICMP explicitly allowed in its initial approved Scope, sets online=true and asserts the observation is accepted before publishing. The same confirmed mutation must preserve enrollment, effective profile and shared descriptor. No existing scope was reconfigured; no runtime/older test changed. Diff check passed. No test result is claimed.

Next: independent dedicated suite, then related seven-file regressions on freshbases06/07 with captured exits, scanner/diff on success and existing native boundaries preserved.
