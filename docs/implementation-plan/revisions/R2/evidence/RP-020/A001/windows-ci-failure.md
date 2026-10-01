# RP-020 Windows CI fixture failure

Functional source `5cf22faf6c009435e8c25343afcf9493f721904d`;
PR head `595a7f78d67b40bcecfbf3ad628f1f060c49bff1`;
checkout `808cd91c67461dbab5741624560d41cef762a2be`.

- Local full Windows:1765 passed,41 skipped,4 known DEF002 strict xfails,
  535.35s, exit0; focused/developer257 passed11.21s.
- CI36813507513/job110213473547:1790 passed,16 skipped,4 xfails,376.67s.
- Desktop Linux36813507562/job110213473700: GUI68 passed1.06s;
  full1801 passed,14 native-Windows skips,4 xfails324.68s; both role builds,
  actual binaries/GUI/install/uninstall profile isolation PASS.
- Desktop Windows36813507562/job110213473380: GUI64 passed/4 skips1.79s;
  **8 failed,1768 passed,39 skips,4 xfails504.93s**, exit1. Builds did not run.

All eight failures are native-key tests attempting enrollment/open of a newly
created fixture. The failing line is owner/DACL precondition at
windows_key_native.py:183, before helper admission. The fixture sets a private
DACL but leaves ownership inherited from the CI process's default owner.
A different default owner under the hosted elevated account is a hypothesis,
not yet a measured SID fact; no SID or protected path needs publication.

Preserve these results. Make synthetic fixture ownership explicit and validate
before/after owner-equals-current-user booleans on the hosted runner. Keep the
production exact-owner check unchanged. Add a fast native Windows gate before
full regression so fixture failures are visible without waiting for the maximum
commissioning-capacity regression. No real credential ACL/owner may be changed.
