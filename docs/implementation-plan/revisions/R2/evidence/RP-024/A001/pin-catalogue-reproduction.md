# RP-024 restored instruction catalogue reproduction

Test source `a47213a90c478b5525a08c12479096baca112fa3`, intent RP0240031. Three synthetic negatives
all failed expected rejection: entry, closure and hash. **3 failed,35 deselected
in0.53s**, exit1. RP024 restore_pin accepted saved metadata after hashing its
requested files and checking current profile policy, without comparing that
metadata to the original immutable commit catalogue. Thus a malformed saved pin
could point to another declared instruction entry, omit a declared file or pair
modified bytes with their new hash. This is a reproduced RP024 defect; RP007
initial selection is unchanged. Fix the restoration boundary, not eligibility or
real profile status. All failures and source commits remain preserved.
