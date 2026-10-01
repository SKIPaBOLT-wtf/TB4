# RP019 corrected product / intermediate validation

Product source `97c7868e6682abbeeea0b58ddd57cd29d9e5f2bd`, PR28 test head `f8e99452955d53b7e251111f5805542b7b536e11`.

Local Windows focused:47 passed,11 Linux-only skips/500.18s/exit0.
Linux CI36808345826/job110197613690:1693 passed,2 skips,4 known strict DEF002 xfails/406.44s.
Desktop36808345955 jobs110197614250 (Windows) and110197614365 (Linux) both completed SUCCESS, including WATCHDOG/FETCHER builds and bundle self-test, GUI smoke and install/uninstall profile isolation. Linux GUI68/2.71s and full1704+4xfail/629.65s. Exact Windows receipt is retained in the journal below.

Progress36808345887/job110197613822 failed after125 development tests passed because event0013 had malformed STARTED metadata. Therefore this validation scope is **FAIL**, not accepted. The code-focused failure DEF022 is repaired; required metadata gate DEF023 needed a separately published repair. No intermediate acceptance or live deployment is inferred. Later final-source validation and exact-tree Progress evidence supersede this failed gate without deleting it.
