# RP-005/A001 reviewed BALLPARK contract

Source: `d3ac272140e6a583777dccb891c7d2aef0e1d4e7`. Tested PR head: `9de0fdaff466d48211ce96286248d90c84b79dc0`. Desktop merge build: `4fff4c5d812a2b57d4bc90331efcb1c4213a08e0`. [PR 12](https://github.com/SKIPaBOLT-wtf/TB4/pull/12).

## Observed checks

Windows Python 3.11: `python -m pytest tests/security tests/development tests/desktop/test_plan.py -ra --basetemp .venv/pytest-rp005-a001`: 152 passed in 13.57 s, exit 0. Current ledger/history against ownership `ec7d051f92d768c6daf7799b799c0826c5b265e5`, public scan and diff checks passed.

[CI 36766835273](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36766835273): 788 passed, 2 optional GUI skips in 10.30 s. [Progress 36766835290](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36766835290) and [36766764677](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36766764677): PASS.

[Desktop 36766835265](https://github.com/SKIPaBOLT-wtf/TB4/actions/runs/36766835265): Linux job 110063006626 passed 67 GUI tests in 2.95 s and 798 full tests in 17.80 s. Windows job 110063006510 passed 63 GUI tests with 4 POSIX-only skips in 2.83 s. Both built WATCHDOG/FETCHER and passed credential-free bundle self-tests, GUI smoke and installer/uninstaller preservation of both role profiles and the peer application.

Artifacts remain in that CI run, not the knowledge archive: Linux ID 11122870337 (310736075 bytes), SHA-256 `018c620361179fd72ca0231293729253288458289f2618a27ee94a01113de90b`; Windows ID 11122345721 (119091964 bytes), SHA-256 `588ddd7fcef9cf288a4a87c7495f51b669e1b14fa6b09a4d2a44b481f0466295`. They are CI artifacts, not approved live releases.

## Per-check review

C1: LOCAL_SCHEMA models canonical installation/domain/device UUIDs, revision, curated alias and display name, role/platform/architecture, per-role launch mode, transport declarations, interfaces/segments and independently sourced observations/capabilities. Missing optional capabilities are UNKNOWN, not implicitly configured. test_no_inference_between_network_ssh_fetcher_and_result and test_each_observation_has_its_own_freshness_and_future_clock_guard establish independent values and exact expiry/future-clock behavior.

C2: catalogue() projects only approved shared fields, removing local installation identity, display labels and interfaces/addresses. llm_projection() produces the separate PRIVATE_LLM schema with freshness categories and no raw timestamps/endpoints/bindings. Closed nested schemas reject secret/unknown fields; public_artifact rejects both private representations. The checked-in JSON Schema bundle exactly matches code. Meaning of curated aliases still requires owner review; no claim that a schema can recognize every secret encoded as a label.

C3: parameterized fixtures cover FLAT, ROUTED, MULTI_SUBNET, VPN, ISOLATED and MIXED, IPv4/IPv6, multiple interfaces, Windows/Linux declarations, ARM64/X64 declarations and co-located roles. They are schema variations, not native hardware qualification. Duplicate display names are allowed; aliases/IDs and same-segment addresses cannot collide. Different isolated segments may reuse an address without merging identity. Address changes preserve IDs and require the next revision. Bad CIDRs, scoped addresses, noncanonical UUID case, alias newline, incomplete provenance/freshness, stale revision and identity removal are rejected with fixed diagnostics.

C4: the contract assigns proposal assistance to a freshly loaded pinned SKILL and owner scope, validation/commit responsibility to active commissioned WATCHDOG, and exact revision/content readback before authority. The pure publication_candidate rejects OWNER/SKILL as publishers, missing owner scope and another installation. It returns a candidate only. Instruction-source verification, backend exclusion/fencing and actual publication are explicitly later RP-007/008/026/029 work; no boolean argument is claimed as a production authentication mechanism.

## Privacy, compatibility and rollback

Only synthetic documentation-range addresses, fixture identities and generic schema values were used. No device, real root, private topology, credential or local operational configuration was read or changed. Review compared tests to invariants and inspected source/diff. R2 plan revision does not imply a released protocol major; existing historical v1 records remain intact. Invalid proposals leave prior values unchanged; removals/domain changes require separate maintenance. Rollback retains previous descriptor revisions/mappings and cannot reinterpret an in-flight operation. A schema declaration does not prove runtime, network or ARM support.
