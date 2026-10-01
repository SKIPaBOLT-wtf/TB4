# RP-021 A001 initial focused validation and source review

Source a39427c4a104e0f61e3ea3231b1a06866848eefd; Windows Python3.11, new isolated synthetic basetemp.
Focused RP006/Windows/Linux policy command:138 passed,32 Linux-native skips,
1 teardown error in0.50s, pytest exit1. Native Windows15 and prior policy tests
are included in the passing total. Linux native cases are not executed here.
The output tool truncated the large failure ID; a separate bounded read of the
persisted log confirms these counts and exact error: ValueError, the environment
variable is longer than32767 characters. Do not publish raw environment repr.
Ledger20verified/one pending action, scanner and diff checks all exit0.

DEF027: the65537-byte size fixture used pytest's automatic payload-derived ID.
Pytest writes the ID to PYTEST_CURRENT_TEST even for skipped Linux cases; Windows
cannot store this length. This repeats the class of historical DEF014 but is a
new RP021 test. Replace only display IDs with empty/oversized; preserve payloads
and assertions. No runtime behavior failed this test.

DEF028: source review found fstatfs0xEF53 described as ext4-only, but Linux
statfs documentation assigns the same value to ext2/ext3/ext4. Thus that check
alone cannot establish the declared ext4/XFS scope. No ext2/3 filesystem was
mounted or exercised. Add bounded descriptor mount-ID-to-type verification and
negative parser cases; retain the fd magic check as corroboration.
Reference: https://man7.org/linux/man-pages/man2/statfs.2.html .

Neither finding permits any real credential/store/configuration change.
