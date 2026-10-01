# Native adapter validation failure
Source 8e934adcfd719af981b7595eeaa5c8bfb6e0b875. The synthetic discovery pytest command returned nonzero and the task shell exited1 before scanner/diff gates. Its capture assignment discarded pytest output on throw, so no reliable test count/duration/assertion or exact pytest exit code is claimed.

A bounded reading of current pytest lastfailed entries under tests/discovery points to test_closed_bounded_provider_json with the oversized X-byte parameter. This is a diagnostic lead only. Six synthetic parser rejection cases will be inspected under the next diagnostic intent with durable task-local output. No native loopback opt-in or home-network query occurred. DEF032 holds RP023C1-C4; no prior accepted step is invalidated by this unproven new-code issue.
