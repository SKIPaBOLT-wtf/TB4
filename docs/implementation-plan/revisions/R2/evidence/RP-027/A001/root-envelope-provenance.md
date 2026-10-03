# Exact root-plan preflight envelope provenance

Source `5b9c339e06d91822c594dca6f276f6634dd2dc48`, checkout `2ca73df1e3929dfea9855481f4c8a7ccfeef1944`. One guarded exact source synthetic Root.begin probe, child exit0. Actual traceback reaches `reconfiguration_roots.py:237` / `begin`, which raises `KeyError: global.summary`. The slot is absent at top level and present inside `records`. Actual shared document and native profile remain unchanged, root WAL absent, SDK moves0. No raw snapshot/private path is published.

This proves DEF-068's source origin at the new denial-only lookup. Fix only the records nesting; retain all prior guards and839 tests. Source qualification is separate from this diagnosis; DEF068 remains OPEN for final C1-C4.
