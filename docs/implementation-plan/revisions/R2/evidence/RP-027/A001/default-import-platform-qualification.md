# RP-027 A001 — corrected default full platform source qualification

Intent RP-027-A001-0132; request published only after verified INTENT. Source `a71954afb45c9e667ae1dd554b6b134fcf7c17c9`; feature head `ab86e71b36a07e88734615d041bf119c71a05316`; actual checkout `5ab3eeb13a6ab7a67dabd944a3a60a2ad95933f0`, merge of that exact head into `ed974c57ce99e54b3a28da79d212c86f07951ec7` verified independently in all job logs.

All three real runs SUCCESS: CI37100513413, Desktop37100513446, Progress37100513478. Complete job/step statuses, full stdout summaries, frozen acceptance fields and published artifact IDs/digests/source are adjacent JSON. No old failed-source jobs were rerun.

| Actual job | PASS | SKIP | strict XFAIL | Full suite seconds |
| --- | ---: | ---: | ---: | ---: |
| CI Ubuntu |2700|27|4|1565.79|
| Desktop Ubuntu22.04 |2723|21|4|1724.89|
| Desktop Windows |2637|107|4|1257.81|

Full default suite includes the original max129 predicate excluded only from the earlier partial139 run. All named required native credential/private first-run/discovery, actual GUI, private owner/FETCHER targeted gates passed as recorded; Progress235 cases plus complete ledger/public/full-history checks passed. All WATCHDOG/FETCHER builds and frozen self-test/GUI/setup/actual fresh install/uninstall/peer and profile-isolation predicates passed on Linux and Windows. Installers stay in GitHub artifacts; they exceed100MiB and are not placed in the home-LAN knowledge archive or deployed.

The four strict expected legacy cancellation failures are the two mode-parametrized reproductions in tests/integration/test_cancellation_race_reproduction.py, already assigned to RP044/045/046. No RP027 skip/xfail was added. Ordinary full stdout reports aggregate skip counts, so individual skip reasons are not inferred; required native/GUI gates and two complete packaged platform results have explicit statuses. These results qualify this source's current implemented behavior, not yet-unimplemented C3/C4 behavior or the whole plan.

DEF069-074 repairs supported by actual ordinary full cross-platform qualification. They remain OPEN until all final C1-C4/common gates. No check accepted: protected two-path folder mapping/native rename/effect recovery, Docs same-object catalogue/commissioning rebind, final descriptor/configuration/epoch/native-profile promotion/stale cache/lease refusal and full composition still required. Actual candidate default activation remains denied.

Next: publish/readback exact same-folder protected resolver/actual native C1 source unit INTENT following same-folder-path-design.md, then native Linux fixture qualification. All prior failed reports and sources retained. No real provider/root/network/router/installed/runtime mutation.
