# RP-025 current ledger failure

Qualification source `86d4d32598616b935a7b8b2623d0c3a28e65767d`; actual clean synchronized checkpoint `d06c3628fa1a4d56457a32476d7d444f18978506`; session68844. Current command `python -m tools.development.ledger` returned **exit1**, public result `LEDGER_INPUT_INVALID`. Complete history command did not start, and no RP025 PR or hosted run was created. Previous focused72/221 tests/scanner/diff remain passing, but no acceptance follows from them.

The closed diagnostic does not prove which current progress input is invalid. DEF-044 preserves the failure for bounded schema/location diagnosis under a separate INTENT. No validator, accepted evidence, journal history or runtime has been changed. Next: inspect exact current schema validation locations and then define a minimal correction only if evidence establishes it.
