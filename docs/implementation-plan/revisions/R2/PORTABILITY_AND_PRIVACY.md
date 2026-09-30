# Portability, commissioning and privacy acceptance axes

This is a required test/design matrix, not a claim of support already implemented.
Every supported cell needs evidence; impossible/unavailable optional capability
must be explicit, and an essential missing requirement cannot be waived silently.

## Data boundaries

| Location | Allowed | Forbidden |
| --- | --- | --- |
| Public source, docs, issues, journals, fixtures and release artifacts | Generic contracts, public source/build SHAs, synthetic tests and sanitized outcomes | Real topology/hostnames/IPs/MACs/root IDs, user/account paths, credential handles/values, raw user payloads/errors/screenshots |
| Protected local operational configuration | Collected topology, exact roots and mappings, per-installation opaque resolver bindings | Secret values in ordinary config when they belong in an approved secret store; copying another installation identity |
| Minimal private shared BALLPARK | Approved opaque aliases, capabilities, timing, revision, safe routing/status references needed by the LLM | Passwords/tokens/private keys, resolver store paths, unnecessary physical topology/account details, embedded LLM instructions |
| Local approved credential/key facility | Authorized secret/key material with scoped access and rotation | Secret export to LLM, debug logs, public artifacts or fallback profiles |
| Program debug/diagnostic outputs, including private ones | Allowlisted state/reason/progress codes and safe provenance | Secret values, full configs/environment/provider dumps; protected topology should not be logged merely for convenience |

The instruction 'no sensitive program descriptions/logs' does not mean the runtime
can work without any protected environment state. Collect that state during setup,
minimize it and keep it separate. LLM-assisted setup requests choices, not secret
values. Fixed helpers resolve local handles automatically within granted scope.

## Platform and topology matrix

- Windows and Linux roles, independently installed and cross-host combinations.
- Desktop per-user, declared headless/service modes, absent user session, least
  privilege, different paths and interpreters. ARM/other OS support is not presumed;
  adapters must report unqualified modes rather than present an x64-only success.
- Same host, separate hosts and valid incumbent plus multiple fallback candidates.
- Flat network, routed/multiple subnets/interfaces, VPN/NAT and restricted broadcast.
- ICMP unavailable but FETCHER active; SSH absent; SSH auth denied; host online
  with a slow or exited FETCHER; credentials absent on a fallback installation.
- Drive API and the specifically qualified shared-folder mode; disconnect,
  eventual visibility, stale reads, missing LLM connector access and conflicting writers.
- Supported authorized DHCP management, no management access, address conflict,
  changed device identity and owner-declined network changes.
- Fresh setup, interrupted first run, later BALLPARK change, safe reconfiguration,
  explicitly confirmed reset and old processes returning after re-enrollment.
- Slow polling, clock skew, sleep/resume, no fresh status and full fixed capacity.

Do not infer network reachability, authenticated SSH, FETCHER presence and command
success from one another. Each fact has its own timestamp/source/validity horizon.
Every target summary includes effective settings, not historical/hardcoded values.

## Installed SKILL boundary

The future installed package has only trigger metadata and a public locator:
repository `SKIPaBOLT-wtf/TB4`, entry `skill/tb4/SKILL.md`, plus fetch-or-stop guidance.
It contains no protocol procedures, state list, payload recipe, topology, timing
constants or bundled operating manual. This is a package contract, not installation
of a new SKILL in this planning task.

The fetched repository entry chooses the compatible operational/setup references,
uses the commissioned BALLPARK projection and pins the selected source revision
for an in-flight workflow. Fetch current source again before the next workflow or
explicit version boundary. Source unavailable/incompatible means blocked, not use
memory. Untrusted result/device strings cannot redirect instruction retrieval.

## Reference limits

GitHub warns that automatic secret redaction is not guaranteed; therefore our
requirement is prevention/allowlisting plus synthetic canary tests and review,
not reliance on masking: https://docs.github.com/en/actions/reference/security/secure-use .
The Drive file API documents version/metadata, but actual backend concurrency
capability must be established at RP-008; no provider guarantee is inferred from
a successful local mock: https://developers.google.com/workspace/drive/api/reference/rest/v3/files .
