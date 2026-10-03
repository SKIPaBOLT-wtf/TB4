# RP-027 A001 native guard requalification

Exact source `98b5948618877160536fca2525fdb7277054d00c` executes51 actual native cases twice:49PASS,2FAIL,zeroSkip. All five new exact operation/sender/election guards pass, as do real one-syscall/same-inode relocation, Unicode, durability ambiguity, pending promotion cuts and stale current-role settlement without old stores. No RP check is accepted.

The kernel no-replace test successfully keeps the foreign destination and original source; its subsequent inspect refusal surfaces as AuthorityError HELPER_UNAVAILABLE, while the test expects the narrower ConfigurationError. The late force test reaches the native transaction context; LinuxSettingsNative.locked intentionally converts any non-SettingsError from its yielded body to opaque SettingsError SETTINGS_STORE_UNAVAILABLE. Its original exception reason is not exposed in the terminal trace, so do not infer that OWNER_SUPERSEDED was verified. Capture actual underlying SQL proof/refusal inside the test and retain no-syscall/original source/UNKNOWN assertions. Existing source guards remain unchanged.

DEF077 records mismatched negative-test exception boundaries. DEF076 repaired native guard assertions pass; original selected regressions are not run after the required step fails, and full acceptance remains held.
