# Versioned BALLPARK environment contract (RP-005)

`tb4.ballpark` and `protocol/ballpark.schema.json` define schema version 1 for
commissioning data. R2 is a development-plan revision, not a released protocol
major. These are pure models and synthetic tests; they do not install, discover
or publish anything on a real device. Existing v1 DOG_TAG/tree evidence remains
historical input. RP-018 onward integrates the qualified commissioning workflow.

## Three separate representations

| Representation | Identity and contents | Boundary |
| --- | --- | --- |
| BALLPARK_LOCAL | Installation/domain UUIDs, revision, stable device UUIDs, curated aliases, display labels, platform/architecture, role launch mode, transport declarations, interfaces/segments/CIDR addresses, independently observed capabilities and facts | Protected local configuration; no secret or credential binding fields |
| BALLPARK_CATALOGUE | Domain/revision, device IDs/aliases, roles/platform/launch mode, declared transports and observation metadata | Private shared catalogue; omits installation ID, interfaces, addresses and display names |
| BALLPARK_SUMMARY | Safe routing IDs/aliases, platform/launch/transport declarations, each capability/fact with current value and freshness category | Private LLM view; no endpoints, exact observation times, credential handles or values |

Public files contain only schemas and synthetic fixtures. Even a valid private
catalogue or summary is rejected by the RP-004 public diagnostic exporter. Actual
bindings belong in a separate local resolver store (RP-006/020/021); neither
descriptor accepts passwords, tokens, keys, paths or credential handles. Aliases
must be explicitly reviewed as nonsecret during setup; string validation cannot
determine whether an owner accidentally placed a secret in a label.

Stable canonical UUIDs identify installations, domains and devices; hostnames,
addresses and display names do not. Duplicate display names are allowed. IDs and
aliases must be unique, and launch modes must match declared roles. Address
collisions are checked within a declared segment. The same address on separately
isolated segments is valid and never merges device identity. Interface names are
local labels. IPv4/IPv6 CIDRs are parsed and canonical address identity is compared.
No drive letter, local path, subnet, router or operating system is presumed.

Fixtures cover flat, routed, multiple subnets, VPN, isolated and mixed networks,
multiple interfaces, IPv6, Windows/Linux and ARM64/X64 declarations, same-host
roles and missing SSH/WOL capabilities. A platform declaration is not platform
qualification. OTHER/UNKNOWN and UNSUPPORTED/UNQUALIFIED are explicit; later
adapters and release gates must establish actual supported modes.

## Independent facts and freshness

Network, SSH transport, SSH authorization, installation, FETCHER liveness,
acceptance and correlated result are distinct observations. Each known value has
its own source, timestamp and validity horizon. Setup declarations cannot claim
runtime availability. Missing fields mean UNKNOWN. Expired values become UNKNOWN
with STALE freshness; future timestamps become CLOCK_UNCERTAIN. At the exact
expiry boundary a fact is stale. A fresh heartbeat may coexist with a failed
network probe; the model does not rewrite either fact or infer SSH authorization.
Declared transport support is not current connectivity or execution readiness.

Capabilities are similarly observed and may be SUPPORTED, UNSUPPORTED, UNQUALIFIED
or UNKNOWN. Missing optional capabilities remain UNKNOWN; no key or another
installation's capability is assumed to exist. Effective operational timing and
relationships are owned by RP-011; validity horizons here do not replace polling,
idle-exit or command timeout settings.

## Proposal, validation and commit authority

1. The owner chooses authorized setup scope. A freshly fetched, compatible,
   repository-owned SKILL helps produce a proposal and records its pinned source
   SHA and expected current revision. It never supplies a secret to the LLM or
   becomes a runtime publisher. RP-007 supplies verified source selection.
2. The active, commissioned WATCHDOG verifies local identity/authority, the
   proposal schema, owner scope, expected revision and device mappings. The pure
   `publication_candidate` models this gate; its authority inputs are trusted
   local control state, never values copied from proposal/device text.
3. WATCHDOG commits the validated private shared catalogue through the qualified
   storage mechanism, then reads back exact revision/content before declaring it
   authoritative. A local candidate returned by this module is not a commit.
   RP-008 establishes exclusion/fencing; RP-026/029 add commissioned changes.

Revision changes must be exactly next-in-sequence against the expected current
revision, within the same domain and local installation. Address changes retain
device IDs. This baseline refuses silent removal/replacement of existing IDs;
later maintenance/reset has separate owner approval and in-flight-work gates.
It retains the previous value without mutating it, so a failed proposal leaves
the old mapping intact. Reverting source does not downgrade a live descriptor or
reinterpret an operation pinned to an older identity/schema contract.
