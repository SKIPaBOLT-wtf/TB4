# RP-027 A001 fixture-only source checkpoint

Source: 0feb433824d43e6f0f6975e8f776316e9723c910

Intent: RP-027-A001-0017, remotely verified at f2ff32b1bfb2a3d41835c8ab11be66d194734fcc.

Exactly tests/drive/test_reconfiguration_maintenance.py changed. The three candidates preserve the incumbent's actual enrollment; the new installation adds only its own synthetic name. Original effect preservation, first-CAS role takeover, inspect-only lost reply and unresolved inherited evidence assertions remain. A separate negative case rejects deliberately inconsistent incumbent enrollment before acquisition or authority write.

No application guard, existing schema, accepted source, runtime, private configuration or workload changed. The local source commit b049e192eda45c427d0ee8661027e7e326ffeb5b remains on its own preservation branch. GitHub exact file/ref readback is verified. No tests ran in this edit unit; DEF-057 and all C1-C4 rechecks remain open.

Next: separately verified exact-source repeat of the recorded22 targets in an owned newly allocated absent fixture root; preserve actual process exit and every case, including failures and platform skips.
