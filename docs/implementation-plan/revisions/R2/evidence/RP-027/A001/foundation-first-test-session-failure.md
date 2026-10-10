# RP-027 first foundation test session: overall FAIL

Source `cfdb45c97ef7c5d177a617a0bf7c87aae929fbcf`; checkout `6b692848a8cd6134adf63ff8bc2d3d20edd25388`; INTENT `RP-027-A001-0008`; actual run `LOCAL-SESSION-45805`. Windows64 Python 3.11.9. Elapsed33.405s; actual child process exit1. [Exact collected cases](foundation-first-test-cases.json) records631 cases:627PASS,4SKIPPED,0 assertion/collection errors.

All new foundation/schema/inspection/private-evidence/maintenance-race/stale-takeover/native-protection/large-Unicode predicates completed successfully, alongside accepted legacy boundaries. Four skipped cases require Linux special objects or pinned-directory replacement; they are not Windows passes. This is not overall PASS: after JUnit emission, pytest sessionfinish invoked cleanup_numbered_dir -> cleanup_dead_symlinks -> pathlib.exists and raised PermissionError `[WinError 5] Access is denied` for an existing global pytest-current temporary alias. Raw traceback/JUnit remain task-private because they include a real host label/account path. No real source/settings/provider/network/profile/credential operation occurred.

DEF-056 records the harness fault. The current code is not proven to have created the denied object; its exact prior origin is unknown. No source repair is justified by this traceback. No attempt was made to traverse, delete, reset protection or reuse that preexisting directory. The task runner used the global default temporary root rather than a dedicated fixture root; a fresh absent --basetemp child can safely isolate the same tests. That remedy remains untested.

Next: a separately verified scoped INTENT for exact-source repeat of the same targets with a newly allocated owned fixture directory. Retain all original failure evidence and test predicates; do not mark C1 or any acceptance complete.

Publication preparation: the unchanged public-data guard rejected 2 synthetic test parameter labels containing path/URL syntax. The exact labels remain in the private report; the public case list identifies those parameters by collection index and stable test name. No guard was weakened and no rejected content was published.
