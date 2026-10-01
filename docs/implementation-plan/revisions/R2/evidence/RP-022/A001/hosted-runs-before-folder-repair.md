# RP-022/A001 hosted runs before the folder repair

Original source f9d2a74102a462c9f8aee35a763ff257306d7118; triggerd3b20e4552de85d6df97a8b6ba8d5853b98d5be5; checkoutab7b5e2380e5c776fde22c4f62cea9812f163558.
- CI36824795489/job110247962607 PASS: native keys33pass0.16s, native setup31pass0.56s, full2004pass18skip4strict historical xfail612.94s.
- Progress36824795496/job110247962355 PASS:172pass4.63s; ledger/history/scanner pass.
- Desktop36824795546 Linux110247963162 PASS:GUI74pass2.25s, native keys33pass0.16s, setup31pass0.55s, full2021pass15skip4xfail613.92s.
- Same Desktop Windows110247962816 PASS:GUI70pass4platform skips2.35s, keys15pass0.16s, setup27pass4Linux-only skips1.26s, full1959pass77platform skips4xfail706.82s.
- Both roles on both OS: actual frozen import/self-test, legacy GUI, setup GUI and installer/uninstaller/profile-isolation PASS. Setup smoke asserts no settings/runtime creation. DEF029 remained in this source; these passes did not establish interrupted desktop reopen behavior.

First repaired source5e3617a42ac732cb3d0d1ff7b5521fa354e0c3a5; trigger1f80ba1c49a839ae91b459de0b0fdd2bd54238d5; checkout60162ac0c9c792f74267bfdf7464c05afd2efb6f, relevant code equality locally confirmed.
- CI36825527613/job110250251350 PASS:keys33pass0.18s, setup34pass0.63s, full2007pass18skip4xfail609.38s. Required isolated SSH fixture executes in CI.
- Progress36825527559/job110250251075 PASS:172pass4.62s; ledger/history/scanner pass at its earlier snapshot.
- Desktop36825527562 Linux110250250880 FAIL:GUI74pass1.71s, keys33pass0.11s, setup34pass0.42s; full1failed2023pass15skip4xfail450.76s. DEF030 independent folder contention; no Linux build/package artifact produced.
- Same Desktop Windows110250251173 PASS:GUI70pass4platform skips2.53s, keys15pass0.14s, setup30pass4Linux-only skips1.32s; full1962pass77platform skips4xfail641.38s. Both frozen roles, setup/legacy GUI and installer isolation PASS.
All these jobs are complete. The 4 strict xfails remain the historical cancellation defect, not new acceptance. Different platform/module/SSH prerequisite skips are not treated as qualification. All fixtures are synthetic; no live migration/enrollment/deployment occurred.

Provider-reported artifact metadata only; not independently downloaded/digest verified:
- Run36824795546 artifact11145655454: tb4-desktop-Linux-ab7b5e2380e5c776fde22c4f62cea9812f163558, 314218396bytes, sha256:7edbc6b4dae51e1c85c99bb5751ec0e2fe7c61298bb08c065f26431661e0536f.
- Run36824795546 artifact11145169511: tb4-desktop-Windows-ab7b5e2380e5c776fde22c4f62cea9812f163558, 120749787bytes, sha256:9a69bda739011701656dff4b4670d6769f5e31ce3055479c59a19d281daa6b28.
- Run36825527562 artifact11146005566: tb4-desktop-Windows-60162ac0c9c792f74267bfdf7464c05afd2efb6f, 120749785bytes, sha256:c9b1a23cb4a4676cc74664d0c05251c19685263cda46dbe861ec1959c1326073.

The first repaired-source validation FAILED as a whole. RP018A002 repair and new complete platform/package qualification are required before RP022 acceptance. Original source passes and Windows passes cannot substitute for failed Linux contention. See folder-contention-failure.md and RP018/A002/lock-order-reproduction.md.
