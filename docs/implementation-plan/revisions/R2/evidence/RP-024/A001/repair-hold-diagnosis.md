# RP-024 repair hold diagnosis

Direct ledger.validate on corrected checkpoint88c759256347b7c8fb6d39c34608df34b69e8949
raised LedgerError at ledger.py517 -> defects.py163 -> ledger.py29. Source line163
requires every active repair recheck in the manifest revalidation_required list.
RP024 is IN_PROGRESS/A001 with an empty list, while DEF038/039 require C1-C4.
The CLI reported the generic LEDGER_INPUT_INVALID rather than this imported
LedgerError; its wording does not establish a separate runtime/input failure.

Populate the current RP024 holds coherently. No accepted predecessor is reopened,
no check is accepted and no journal/evidence history or validation rule changes.
Diagnosis printed only exception type and repository file/line/function identifiers;
manifest read printed only step/status/hold list. Both diagnostic reads exited0.
