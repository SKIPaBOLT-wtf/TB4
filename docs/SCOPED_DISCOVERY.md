# R2 scoped discovery foundation

This unreleased RP023 model operates on protected local observations. It does not
scan a network, enroll devices, publish a shared record or change an installed v1
profile. Native collection, durable settings and fixed-authority publication must
be qualified before RP023 acceptance.

Commissioning selects exact interfaces (name and native index), canonical subnets
and permitted methods. Interface and subnet must both match. Empty scope means
isolated, not scan everything. A native adapter must freshly verify interface
identity before using this policy; an old index is not current authorization.
Routed and IPv6/VPN observations are representable without broadcast or ICMP.

Each observation carries source/time/validity. Neighbor-cache existence is not
current online proof; absent ICMP or failed observation is not proof of OFFLINE.
Stale, future or untrusted-clock observations cannot refresh a target. Network
observation never implies SSH authorization, installed software, FETCHER readiness
or a successful command.

New records receive a random catalogue UUID and an opaque slot alias. The protected
candidate must be durably saved before the identity is published. Names, hardware
hints and addresses do not grant identity or trust. An unknown endpoint's record is
provisional: continued observation is not proof that the physical device stayed
the same. A changed/lost hardware hint, repeated hint on another interface or
conflicting verified identity is quarantined without reassigning a known target.
Untrusted observations cannot refresh an enrolled endpoint as that trusted device.

A TrustView is supplied by a separately qualified enrollment adapter. It is not a
JSON READY flag, secret, signature or security boundary for hostile local code.
Only a fresh verified fixed-helper identity proof associates multiple addresses
with one enrolled catalogue identity. This model cannot create such enrollment.
Removing current enrollment from the trusted view immediately removes that trust
from the shared projection. RP025 will supply actual enrollment composition.

All catalogue and quarantine slots are bounded. Full capacity preserves mappings
and marks explicit overflow; there is no implicit eviction, OS rename, address
reservation, per-device file or dynamic exchange-object creation. Repeated
ambiguity at the same endpoint updates one retained quarantine slot. Resolution
requires later explicit review; discovery does not clear quarantine itself.

Public/shared projections omit private interface names/indices, addresses,
hardware/name hints and installation identity. Protected images keep only bounded
observations and mappings and reject copied foreign installation/domain state.
Errors/status use closed values. This model's projection is the minimal discovery
record; later descriptor/enrollment composition must preserve RP005 fact rules.

Rollback keeps prior mappings. A new scan cannot reconstruct or overwrite a lost
trusted mapping; ambiguous observations remain inspectable within fixed capacity.
No home-device or network access is performed to implement or test this model.

