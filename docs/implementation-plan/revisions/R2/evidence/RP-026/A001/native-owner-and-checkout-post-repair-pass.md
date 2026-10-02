# Post-repair native owner and canonical checkout diagnostic

RP-026 / A001. INTENT RP-026-A001-0043, verified commit bd1191b16e0eeb4bec6d2effda8bb9c1f141c765. Exact implementation source 6b1a4d19d5e4f349823b4367b5e19b4b7fe8a657. Actual platform win32. Fresh run rp26-native-and-checkout-002. Diagnostic process approximately 3.486 seconds; helper structured result PASS and its actual classified exit 0. The shell cleanup exit alone was not used as evidence.

Procedure: run the existing task-owned rp26-native-owner-diagnostic helper against the clean exact task branch. It creates separate new local public clones, command-local autoCRLF true/false and empty hooks, and compares the unnormalized actual bytes of all seven catalog input paths. It then uses actual native protected setup/table leaves and the existing Discovery.observe adapter with synthetic commissioned provider, clock, capabilities and ownership grant only. No live topology/service/account or pending fixture was reused.

Observed:

- autoCRLF true: seven checked inputs, zero mismatches.
- autoCRLF false: seven checked inputs, zero mismatches.
- Native observation returned OBSERVED. Full original current-owner checks returned PASS/PASS/PASS.
- Durable discovery and table each contain one device; pending transaction is absent, table read succeeds.

Earlier failed diagnostic and three CRLF digests remain preserved in native-owner-and-checkout-reproduction.md. This receipt does not normalize away catalog errors or claim network provisioning. Native integration negative/regression/Qt/source gates and full hosted Windows/Linux packaging are next. C1-C4 and DEF-049 through DEF-053 remain held. Only closed structured synthetic facts are public; raw native binding/private frames and fixture paths remain task-local.
