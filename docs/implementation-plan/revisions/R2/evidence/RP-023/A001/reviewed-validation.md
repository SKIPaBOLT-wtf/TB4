# RP023 A001 reviewed acceptance

Source `a423b69e03bd43c756cfb1077a5920fed93b42de`. [Hosted qualification](hosted-validation.md), [focused native/persistent validation](persistent-discovery-validation.md), [Linux CI and ledger](ci-validation.md), and preserved diagnostic records establish this attempt. RP023 remains IN_PROGRESS until final ledger/main-base review and authorized merge; old failures/DEF032-036 remain visible until coherent acceptance.

## C1: authorized observation and freshness

Scope.permits requires both exact native interface index and owner-approved canonical subnet; commissioning package validation checks every interface network is contained in selected setup scope. NativeNeighbors verifies fresh name/index before and after bounded cache reads; fixed-helper composition prevalidates endpoints and rechecks current role at each invocation. Only native loopback is actually probed in CI. Scoped filters, parser/output/time bounds, refused broad queries, absent ICMP and stale/future/untrusted clocks have named tests. Cache presence does not imply ONLINE/OFFLINE. Publication now preserves newer shared probe source/time/TTL and ages expired/future facts conservatively; all three reproduced failures and newer-local-positive control pass.

## C2: durable identity without automatic enrollment

Catalogue mints a random identity and opaque alias once into the protected candidate. Discovery saves it in the existing native setup frame before any shared plan. Restart/cancel/rollback/local-write-failure tests establish persistence and no shared write before durable readback. Shared identities are adopted without copying trust; occupied identity conflicts block without remapping. TrustView is supplied by separately qualified trusted enrollment code; network hints cannot construct enrollment. Private endpoint/name/hardware data is omitted from shared catalogue and closed status, with synthetic canary assertions.

## C3: ambiguity and changing endpoints

Foundation tests distinguish duplicate hostnames, changed/lost/repeated hardware hints, endpoint ownership conflicts and older observations. A separately verified fixed-helper binding can associate one enrolled identity with multiple interfaces; unknown observations cannot refresh an enrolled peer. Routed IPv4 and IPv6/VPN cases validate scope/provenance behavior using synthetic trusted ports, without assuming broadcast reachability. Full catalogue/endpoint/quarantine capacity retains previous mappings and marks overflow; it never evicts a trusted identity or reports failed probes as offline.

## C4: existing bounded records and owner-safe publication

RP019 catalogue entries already contain artifact references and enrollment seed. Discovery preserves those bytes and adds one nested minimal observation projection. First assignment protects all existing work/result/cancel/ack/status/artifact slots and requires them free; refresh of the same identity preserves UNKNOWN jobs. Quarantine coalesces closed reasons in existing FREE slots and preserves foreign/UNREAD/retained entries. Synthetic actual Docs request adapters verify only exact metadata reads plus the existing authority CAS; no create/list/delete or OS/DHCP operation is available. The fresh actual Windows/Linux private-settings test verifies no per-device file. Persisted exact plans reject owner/authority/slot/artifact/generation tampering and recover by INSPECT only. Stale/forced takeover and post-durability supersession tests prevent subsequent old-owner publication without any all-device acknowledgement barrier.

## Compatibility, privacy and rollback

Legacy installed profiles and default DenyActivation are preserved. This step adds unreleased composition, not a release, enrollment adapter or live migration. General setup cannot rebind discovery identity/scope/root or roll back mappings/pending writes; cancellation preserves them. A possibly admitted external read may finish during takeover. No private observation/topology, real token/key or user-path log was published. Scoped actual native evidence and full platform regressions supplement synthetic invariants; counts alone are not the acceptance basis. All four historical DEF002 strict expected failures remain outside this step.
