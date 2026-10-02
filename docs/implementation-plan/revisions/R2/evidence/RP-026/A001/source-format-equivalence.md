# Canonical EOF and instruction digest closure repair

INTENT: RP-026-A001-0033
Prior semantic/target source: 9e986b3ff62c18facc81e06a7b1b521209a899b9.
New exact public source: aba77c9aa9df314e3088dfb388a84a7f7011cb6a.
Own local draft e0308b38e7d5a6061a8e0794be82d9b008e8e5b5 retained.

All 13 edited files were new relative to the branch main base. Their normalized public LF body bytes are identical excluding final newline count; each now has exactly one final newline. Only the new device-description guidance digest changed in the UNRELEASED catalog. Its entry/profile/build eligibility and other file/schema digests were verified unchanged. All 14 files remotely read back; no functional assertions/source or installed SKILL changed.

| Public file | Before SHA256 | After SHA256 | Body equal excluding EOF |
| --- | --- | --- | --- |
| docs/NETWORK_TABLE_CONTRACT.md | 55453a7be8caf04966234a6a7f9b89d115fba1f6d3800288eed0b0e26dc927f2 | e705c792069207066f468006ab2de39ab639dceb4bf70604590a3f015dc341d0 | true |
| packaging/skill-pointer/tb4-describe-device/SKILL.md | 46353f8b0a388a094e76eabe9f01b28358b3562b9fcf55a21d47e9d9c5c7808b | 10944ab9c61bb9e1d566316910b22795ac8aad197dbf50bd7fa2355b9d8c2005 | true |
| skill/tb4/operations/device-description/SKILL.md | 1fb1e2e18479a91585165e187eb761b80915794782c977403b3ca45f5e0a23f4 | b7528e9003fe9b599845f4261f1760296773a2d40af39d2fcdb453aca8faac36 | true |
| src/tb4/desktop/network_table_dialog.py | 4f39a7161ad4a2f6e96969dd7d887cd945c2df08243099e2714165a54f8b4ea9 | e72080c98878fc182b1db8312c4e2129eb2f61ad4f772a6e42f2a92e12977ed6 | true |
| src/tb4/network_description.py | 8cffdd840f257ba46c33d234202db899ef997234c098fe902289be5dbf15e4cf | 2dc6bc941ce5ecd9a99c7412a71e356f3363802e64c2f46aa8f5776b8e7e9470 | true |
| src/tb4/network_table.py | a0d8b2a0525171e1579ea23b2dbb1d9364f67b20531049b068918bf5935488fd | d469729ea7f9538bba8d852d1a1e6007d2bd4edbabddae4295a1f917f59e2d20 | true |
| src/tb4/network_table_store.py | fe99bc62315c5f9ae5226f9a79c0d36580c6c2cbf489ece1d1b723ec72cf27a9 | c285b14e34c6043bfd97e78655f9c4594a034a87f13b7e590de5a5e504e4ec34 | true |
| tests/desktop/test_network_table_ui.py | 8306b38ab9982f9e6765c20c04a53b819f6cbf239c6503c604d325cd7844c7d0 | 47951689c3ea55c932a3f3176cdbb5ae343611b2ebffe20bcca6c9cc6fc195bb | true |
| tests/drive/test_network_description.py | 27ec8a9d8c67a24b696dd2ec6e890ecb109668424d28f38fc305e53f43bfe9b1 | 826401089152e9c62ee30da186f4fd62ff407603e9384409fc0640f8e310437c | true |
| tests/drive/test_network_table_schema.py | 1b9625fee9d095c17c93b7dfd52fbdc476215c6f8881dbe6438414967895c976 | ea3829c4e8652ed24d65bd07d1b5b1ca71e50c9dc47a8ce46d6981842f8f03b3 | true |
| tests/drive/test_network_table_store.py | a20d51ded685c9be90e6fcc13998ee7484f982743f7230d3f99376765a5a1aaf | a9c368bd426d0cd27017cf782dea1769457b4b43dc0f0b292ec050077abf71e2 | true |
| tests/network_table_support.py | bae6c5b225c1cdbfeaa17189250d498355f2601857ab6be2dea80fdfa7c4f8dc | c90381d52dbe7b857bdd64a3507c498b1580a495ccbbc12c742eb1d2399ae515 | true |
| tests/security/test_network_table_native.py | da127a6c7cd2e422102f967422d4ac73def88a8dfd904806459b4e15ce71a98f | e22407407bd8f3763d20383b3c043bf669a4f179aa1d94e45dcb1479adf8ada5 | true |

Existing 338-pass Windows functional evidence remains tied to its original exact source, and the diff exit2 remains retained in targeted-functional-pass-format-failure.md. This receipt proves only format-equivalent source/digest preparation. Latest-source instruction/schema pin tests, SKILL/diff/privacy/history checks and native hosted Windows/Linux full-suite/build/distribution acceptance still must run. C1-C4 and DEF-049/050/051 are not accepted or closed.

Diff/privacy/compatibility review: existing protected native binding/locks and discovery policy unchanged; local table uses typed closed private facts, notices contain opaque identity/status only; local owner approval does not enroll FETCHER or publish shared grants. Instruction closure remains UNRELEASED with no build grant, no implicit live activation. Linux replacement/removal guards preserve default/custom/retained table data and refuse unavailable inspection. All rollback data and exact pending operations survive; no router/host network operation, private credential/host/path/topology or actual deployment data was touched/published.

Next: published latest-source instruction/SKILL/diff/public-contract and draft-PR hosted Windows/Linux full regression/build/installer qualification INTENT. No routine approval is required under existing public development authority.
