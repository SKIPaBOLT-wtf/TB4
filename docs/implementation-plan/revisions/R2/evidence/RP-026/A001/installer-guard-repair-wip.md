# Linux table-inspection failure guard - repair WIP

Repair INTENT: RP-026-A001-0028
Source: 9e986b3ff62c18facc81e06a7b1b521209a899b9
Prior reproduced source: f7982df61404257affa794c4c355cdba3841d305, installer-inspection-failure.md.

Both guards check the actual find status before the empty-result test. Failed inspection emits closed text with no directory/path echo and stops before staging/replacement/removal. Successful no-data handling and default/custom/nested table presence guards remain. Added valid-candidate isolated regression for both install/uninstall and both forced search failure/non-root directory permission loss; root permission cases explicitly skip and need hosted unprivileged Linux evidence. No real permission repair or installer operation ran.

The public contract now explains that active location changes retain their old table: a retained installation-local table copy also blocks replacement/removal, and must be safely preserved outside before the installer proceeds. No automatic delete/copy of private user data is introduced.

Own local draft 391797d28dc4f3856b65471fb77192cdde4f17db remains preserved. Four modified public files were remotely read back. No tests or live deployment action were performed under this source-edit unit. DEF-049/050/051 and all RP-026 C1-C4 remain held. Preserve failed diagnosis and both prior Windows failed qualification receipts.

Next: fresh Windows targeted/native/Qt and SKILL/history/privacy gates plus a new independent isolated Linux diagnostic recheck; hosted unprivileged Linux/full native Windows build/installer matrix follows under its own INTENT. No new router/device/IP authority is involved.
