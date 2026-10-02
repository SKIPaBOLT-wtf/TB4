# RP-026 network authority decision proposal

Status: **AWAITING_OWNER_DESIGN_DECISION**. No network-management implementation or RP-026 check is accepted. [RP-026.C1](../../steps/RP-026.md) explicitly requires a selected supported authority and authorization; [R2 decision gates](../../README.md) name RP-026 authorized network management. The owner baseline leaves concrete router/DHCP integration open. Ordinary implementation and the approved native-Docs storage design do not choose this separate architecture or permit live network changes.

## Recommended decision: DHCP authority first

Keep target hosts as DHCP clients. Stable addressing is requested through a deliberately commissioned existing DHCP authority and a fixed trusted management provider adapter. Provider/authority identity, address pool, routes, exact stable device identity, access bindings, granted operations and rollback snapshot are protected first-run configuration. Public TB4 uses typed bounded provider capabilities, never a hardcoded owner router/address/account or raw LLM commands. Start with one explicitly selected, already available provider integration; additional provider families require separate qualification. Do not install a new DHCP server, alter a subnet, or silently replace an unavailable provider with host-static configuration.

The private canonical archive describes an existing reservation management API and reusable bounded management route. This supports a concrete possible integration; it is historical documentation, not current reachability, a TB4 commissioning binding, or permission to write it. No actual router/API request was sent in this review. Exact provider selection and live capability checks remain local and belong to subsequent approved commissioning/qualification.

## Alternative: managed host first

Deliberately support native host-static configuration through owner-selected Windows NetTCPIP and Linux NetworkManager adapters. This changes interface address/DHCP behavior on individual hosts and requires a confirmed reserved/excluded address policy, exact local interface identity, out-of-band recovery, privilege and private prior settings before any application. It is a different product behavior from preserving DHCP clients and is not a hidden fallback.

Microsoft documents that New-NetIPAddress disables DHCP on an already DHCP-enabled interface (Microsoft Learn, NetTCPIP / New-NetIPAddress, Windows Server 2025 reference, read 2026-10-02) and that address usability depends on duplicate-address detection. NetworkManager documents per-device checkpoint rollback (NetworkManager 1.48, org.freedesktop.NetworkManager reference, read 2026-10-02) and connection Update2 (NetworkManager latest, org.freedesktop.NetworkManager.Settings.Connection reference, read 2026-10-02). These establish interface/API semantics only, not a qualified TB4 adapter, current installed capability or safe live assignment.

## Common contract whichever option is chosen

1. C1: first run selects a supported exact authority and owner-scoped provider/operation/target permission; missing/unsupported access stays visibly NOT_PROVISIONED without claiming this required feature complete.
2. C2: read fresh provider settings, current reservations/assignments and exact stable identity; reject conflicts or uncertain pool/identity. Compute one minimal reversible before/after plan. Preserve unrelated DHCP/DNS/routes/interfaces and save private rollback and exact pending operation durably before any write.
3. C3: owner approves that exact plan separately from the design. Recheck WATCHDOG role/force request, scope, identity, credentials and provider before admission; apply once through the fixed trusted adapter. Verify actual authority readback and observed assignment separately. Lost reply/restart/takeover retains UNKNOWN and permits inspection only, never blind replay. An already admitted change may complete after role loss; no sink-ACK barrier is introduced.
4. C4: test absent/unsupported authority, permission loss, conflicting/reused address, unstable or changed device/interface identity, stale provider revision, partial application, failed/private save, failed assignment readback, cancellation and exact rollback. Use synthetic fixtures and an explicitly isolated native/provider sandbox; no home-network experiment before separate scoped approval.

LLM/public views expose opaque target/provider aliases and closed provisioning status/freshness only. Real endpoint/MAC/interface/account/pool/credential/rollback data stays protected. Existing descriptor, enrollment/profile, generations, artifacts and UNKNOWN work must survive. One instruction/protocol pin governs an operation. Full topology is never a public fixture.

## Requested owner choice and permission limits

Approve the recommended **DHCP-first design and isolated implementation/tests**, or choose **managed-host-first design**. This decision selects the product architecture for RP-026. It does **not** authorize changing any running router, DHCP reservation, host address, network settings, credentials, live deployment or migration. Those actions still need an exact reviewable plan and their own existing or new scoped authorization.

After a choice, append the decision and responsible-step amendment; implement the smallest chosen typed adapter/workflow and qualifying negative/native tests under new INTENT/OUTCOME units. Preserve this proposal and all earlier history. No broad context or password/key needs to be sent in the conversation.
