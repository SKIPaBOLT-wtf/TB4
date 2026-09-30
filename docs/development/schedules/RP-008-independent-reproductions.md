# Scheduling exception while RP-008.C4 awaits owner decision

Recorded 2026-09-30 under R2 README and WORK_INSTRUCTION section 2.

RP-008 has a reviewed storage/automatic-fallback design decision that cannot be silently adopted. RP-009/010/015/016/018 remain dependent and must not start. RP-013 and RP-014 each depend only on VERIFIED RP-001, RP-003 and RP-004. Their deliverables are isolated synthetic reproductions of already recorded DEF-001/DEF-002, not production repairs, protocol selection, live replay or deployment.

After publishing and merging the RP-008 partial evidence/blocked checkpoint, work may proceed sequentially to RP-013 then RP-014 while retaining RP-008's owner decision in the cursor. No dependence on the proposed Docs ledger is introduced. The original pilot remains untouched. RP-015 and RP-044/045/046 fixes still wait for their actual prerequisites. This is a scheduling exception only; no requirement, historical check meaning or deployment authorization is amended.
