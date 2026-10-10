# RP-027 A001 — actual isolated platform collection failure

Intent RP-027-A001-0125; source `5665870eb003bb335dc61ced8472f8809d464cf5`; PR36 exact head `bbcfb19cad5dffa59c3686a72a4ac5db6acab0e9`.

The three recorded GitHub runs reached terminal outcomes: Progress37099512153 SUCCESS, CI37099512167 FAILURE, Desktop37099512163 FAILURE. Exact jobs and step statuses are adjacent. Full regression collection failed in the same four files on CI Ubuntu, Desktop Ubuntu22.04 and Desktop Windows. Two repository fixture modules were imported as unqualified top-level modules before their directories became pytest import paths: test_credential_contract and reconfiguration_support. Actual modules exist at tests/security/test_credential_contract.py and tests/reconfiguration_support.py. pyproject.ini_options adds only src. The custom scoped runner's helper search path masked these errors; full ordinary CI exposes them. This is test import portability, not a missing production dependency.

No full-case passes or build/package results are inferred: build/upload steps were skipped after collection failure. Prior native credential/protected first-run/discovery, real GUI and owner/FETCHER targeted prerequisites passed; complete progress ledger/public/history checks succeeded. Raw logs and filesystem/profile diff material are omitted; exact closed error codes/modules/jobs preserved. New DEF074 OPEN.

Next: publish/readback exact4-path import repair INTENT, replace only the four RP027 unqualified imports with repository-qualified tests fixture imports; no assertions, production paths or accepted old tests changed. Preserve source and run default full collection without test helper PYTHONPATH, then same real CI/native/full/build jobs on repaired source.
