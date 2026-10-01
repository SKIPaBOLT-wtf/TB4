# RP023 hosted platform and distribution qualification

Reviewed source `a423b69e03bd43c756cfb1077a5920fed93b42de`; PR32 trigger `f975511e8d7c4eafeba51d570c1d391e229a9aa9`; actual logged checkout `c2fe144624487711a3efcbb874213d3c59efcf7c`. Exact Git runtime/test/workflow/tools/protocol/config/packaging equality passed. Documentation-only later heads require final ledger review, not invented runtime evidence.

| Gate | Run / job | Reviewed result |
|---|---|---|
| CI |36838966326 /110293145041|SUCCESS:2124 passed,20 skipped,4 strict historical xfails,616.64s; Linux native keys33,settings34,loopback2; required isolated SSH and scanner|
| Progress |36838966397 /110293145097|SUCCESS:196 passed5.27s; current/main-base ledger PASS22verified/sole pending0038; scanner|
| Linux Desktop |36838966401 /110293145574|SUCCESS:2141 passed,17 skipped,4 strict historical xfails635.72s; Qt74,keys33,settings34,loopback2|
| Windows Desktop |36838966401 /110293145291|SUCCESS:2077 passed,81 skipped,4 strict historical xfails720.56s; Qt70+4POSIXskips,keys15,settings30+4Linuxskips,loopback2|

Both platform dedicated discovery gates explicitly enabled TB4_REQUIRE_NATIVE_DISCOVERY=1. Linux actual two-loopback tests took0.04s; Windows8.53s. Full suites skip those two opt-in cases, covered by the preceding required native gate. Windows/Linux actual native settings and credentials use fresh fixture data; no home configuration or device mutation. Strict historical cancellation/deadline xfails remain DEF002 for later RP044-046 and were not altered.

Windows CPython3.11.9, Linux3.11.16; Qt6.11.2/PyInstaller6.22.3. Both WATCHDOG and FETCHER frozen bundles on both OS recorded PASS for bundle/core import self-test, legacy GUI smoke, first-run setup GUI smoke and installer/uninstaller profile isolation. Build tooling includes all tracked src/tb4 data and derives dependency imports without copying private settings or test directories.

Artifact metadata returned by GitHub (not independently downloaded/rehashed):

- Linux11151037938,314260200bytes,sha256:a14a8603bdaa77df6728cf11fa1abf0387e30459d160d8b71f5b795da7d830cd.
- Windows11151272986,120779903bytes,sha256:ac8b2b8a89b68798c3bca8bec14a78a8b75f6c38f495b845e79ae3802bf21df4.

The uploaded distributions/checksums/acceptance records are CI artifacts, not a production release or installed deployment. Actual qualified builds are x64. ARM64 and live routed/VPN credential/topology qualification remain later deployment gates.
