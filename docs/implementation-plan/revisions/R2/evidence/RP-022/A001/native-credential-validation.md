# Native Windows credential restoration

Source: 7e016dd0ff555ecf3bf79f2033bae7b292715ef2.
Intent: RP-022-A001-0016.
Actual Windows x64 Python3.11.9, fresh synthetic pytest-owned private files only.

Command: `python -m pytest tests/security/test_credential_persistence_native.py -ra --basetemp=../rp22-native-credential-fixture-001`.

Observed: **4 passed in 0.12s**, exit0, no skips.

The test selected an actual native protected external key file, exported metadata to the actual protected settings transaction, reopened settings through a new native adapter, constructed a fresh native key store/resolver and restored the same opaque handle/locator/original file version. Same source version returned READY; changed source returned REVOKED; revoked binding remained REVOKED; expired binding remained EXPIRED. No callback used the key, no SSH/provider access, no real credential. Synthetic key material was absent from settings.json; status omitted path/opaque handles. No file was copied to recover the key.

Actual Linux execution remains outstanding in CI. This evidence does not accept RP022 model/UI or a live runtime.
