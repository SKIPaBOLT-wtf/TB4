# RP-024 foundation retest

Source `6c341da01ddf2e01b45a6aa078e47a9a64754cee`, intent RP-024-A001-0007.
Windows Python3.11.9/PYTHONUTF8=1, fresh isolated task base.
Five selected files: **183 passed in 5.73s**, pytest exit0.
Public scanner clean/exit0; full branch whitespace check exit0.

Reviewed test cases cover blank/partial/unknown choices, nonsecret-only proposal
schema, malicious text/authority injection, staged exact owner decision without
shared writes, unchanged prior active descriptor, wrong binding/schema,
revocation/immutable instruction closure, restart/cancel/rollback and unknown
operations. DEF038 stimulus repair exercises an actual revision change and
preserves the rejection assertion. Existing discovery/first-run/loader/descriptor
regressions also pass. These are foundation gates only; C1-C4 acceptance awaits
shared publication and full required hosted/native/frozen validation.
