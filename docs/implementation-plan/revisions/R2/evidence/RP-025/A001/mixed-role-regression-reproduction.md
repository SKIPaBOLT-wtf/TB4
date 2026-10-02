# RP-025 mixed-role regression reproduction

Source `098fa945dde8b43cd9ce98feb651b237817afe70`, clean checkpoint `6bfdca5a3448dfffaa6e28f207aa95644d247997`. Production summary is unchanged; new tests use real initial owner proposals/approval on fresh capacity-two synthetic commissioning. Command: new enrollment file with `-k 'summary_pages_only or watchdog_only_role or summary_cannot_hide' -ra`, freshbase08.

Actual **4 failed,3 passed,48 deselected in2.34s,pytestexit1**. Four mixed/combined/all-WATCHDOG projections fail: incorrect next_start includes a non-FETCHER slot, or the current view rejects a WATCHDOG-only role. All-FETCHER pagination, non-FETCHER registration denial and bound-ineligible role rejection pass. This is measured expected failure reproduction, not passing acceptance. No prior assertions changed and no live state was used.

Next: select only eligible approved FETCHER slots before pagination; reject bound ineligible roles; preserve target registration checks, budget, identity and own-credential boundaries. Re-run these same seven cases and full focused suites after exact-source repair.
