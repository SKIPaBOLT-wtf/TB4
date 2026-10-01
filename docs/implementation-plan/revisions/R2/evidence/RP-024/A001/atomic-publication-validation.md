# RP-024 atomic publication validation

Source `c5b7e7500c2cc6583b4deff03708d8d2cf388474`, intent RP-024-A001-0011.
Windows Python3.11.9/PYTHONUTF8=1, fresh task pytest base: **208 passed in8.64s**,
exit0. Scanner clean/exit0; fullbranch whitespace check exit0.

The25 publication cases use the actual native Docs authority adapter against a
synthetic provider. Exact one-CAS publication changes only selected catalogues,
registry and settings; prior artifact/discovery/enrollment and UNKNOWN work stay
unchanged. Reviewed negatives include revoked guidance after durable save,
pre-write stale/forced owner, lost reply and successor owner, newer remote revision,
local persistence failure, cancellation/restart, foreign root/schema, oversized
record and tampered frozen plans. Restart never dispatches another write. Local
active descriptor changes only after exact same shared revision/provenance confirms.
Discovery refresh preserves compact descriptor fields; its saved plan cannot alter
them. Native Windows protected-file restart passed with an isolated fresh profile.

These focused gates do not prove live provider deployment, packaged desktop
composition or complete Linux/Windows regression. RP024 remains IN_PROGRESS.
