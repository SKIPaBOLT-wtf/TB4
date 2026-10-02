# RP-025 discovery stimulus follow-up

Exact source `40671f9e125674ae671a385e58583ef614a767e3`, clean local checkpoint `78d3176e773f1c7df5ea748b44a8a87c2ac88d94`. Dedicated two-file suite: **71 passed, 1 failed in 10.93s, exit1** on freshbase04. Seven-file set/scanner did not run.

Remaining `test_discovery_refresh_preserves_enrollment_and_effective_profile` received `NO_CHANGE` rather than expected `CONFIRMED`. The prior repair chose class-valid ICMP, but the existing default Scope.methods admits only NEIGHBOR_CACHE, and Observation.online defaults false. Catalogue.observe correctly rejects a probe outside approved scope; no changed shared network evidence exists. This was an incomplete DEF-043 stimulus repair, not a proven runtime fault. Discovery.configure explicitly prevents silently changing the existing scope.

Next repair: build this specific test from a new fixture with ICMP explicitly present in its initial scope. Submit an online ICMP observation at the advancing trusted clock, assert it was OBSERVED before publishing, then verify the same confirmed update preserves enrollment, effective profile and descriptor. No reconfiguration of an existing authority or live network is included. Keep all failed history and C1-C4 holds.
