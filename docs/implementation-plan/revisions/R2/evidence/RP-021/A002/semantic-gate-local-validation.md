# Semantic gate harness — actual local qualification

Sourcea6b6dfaf728de283991ec8a34ac2c4a93d51f443, tested checkpoint18e5656416ef82ec3ac5c6d14f6a8db122007203; actual Windows x64 CPython3.11.9 development environment. Recoverable exec10086 completed all seven gates exit0 with separate fresh task-owned pytest basetemps and hostname-stripped JUnit. No native Linux test or remote job was claimed from this Windows run.

| Exact procedure | Measured result |
| --- | --- |
| `python -X utf8 -m pytest tests/protocol/test_security_contract.py -ra --basetemp=<new-synthetic-root> --junitxml=<sanitized-task-artifact>` | 151pass,0errors/failures/skips; JUnit9.196s |
| Same invocation for `tests/protocol` with its separate fresh root/XML | 492pass,0errors/failures/skips; JUnit13.227s |
| Same invocation for `tests/development` with its separate fresh root/XML | 235pass,0errors/failures/skips; JUnit28.166s |
| `python -X utf8 -m tools.development.ledger` and `--base e4a78d81cd42dc53b379b868631ba3845a0b3e36` | bothPASS20verified/64steps; onlylocalqualification0025pending |
| `python -X utf8 tools/scan_public_repo.py` | clean exit0 |
| `git -c core.whitespace=cr-at-eol diff --check e4a78d81cd42dc53b379b868631ba3845a0b3e36 HEAD` | wholebranch exit0, per-command declared CRLF method; no config/guard/history mutation |

Semantic positives cover real CURRENT-selected keys/definitions under equivalent block/inline/JSON; all37missing-gate comment disguise controls reject despite matching the original literal text search; wrong definition and duplicate keys reject. Exact matrix-export/nonempty checks remain and every other original security-test function/class AST is identical to priorb4fd7. Runtime/policy/native/helpers/workflow/protocol/config/packaging/SKILL/pyproject/enrollment-doc closure is byte-identical to priorb4fd7. This is test-only supplemental coverage, not a changed role/policy contract.

Exact historical RP012/A001 C1 receipt sourcef57c88138e35130379b9a040714836ac8de702a3 was read through Git and still contains all current required real gate keys with their exact canonical definitions. Historical receipt/source meaning remains true; it is not falsely claimed to have executed the new negatives. All failed full/default-diff/preparation attempts remain separate immutable evidence. Current RP021–025 holds and DEF042–048 stayOPEN pending the new complete hosted native/Qt/full/frozen/both-role package qualification and per-check review.

Privacy: only public source/run/test names, allowlisted summaries and synthetic inputs here. Raw local fixture paths, JUnit framework hostname and provider/environment output are not published. Rollback retains external keys, private setup, exact uncertain operations, source and accepted-build history; revert only unaccepted supplemental test source if necessary. No release, live deployment, network change or workload replay occurred.
