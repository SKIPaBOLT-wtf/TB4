# Protected metadata codec validation

Source: da3075e02f1cb013489766763b39d847728df9a3.
Intent: RP-022-A001-0012.
Actual Windows Python3.11.9 running portable synthetic adapters only.

Command: `python -m pytest tests/security/test_credential_persistence.py -ra --basetemp=../rp22-credential-fixture-001`.

Observed: **18 passed in 0.08s**, exit0, no skips. Local source bytes supplied to the remotely verified source commit were unchanged before this run. Concurrent model/commissioning session65190 inputs were unchanged.

Reviewed: exact opaque reference/version across a fresh native-session model; changed version remains REVOKED, expiry remains EXPIRED; missing/denied/trust/revocation remain unavailable; foreign installation/principal rejected; malformed shapes/purposes/expiry/version/secret fields cause no partial restoration; an existing resolver is not overwritten. Metadata contains a protected synthetic path, never synthetic key material; public reports omit both paths and handles.

This is codec conformance only. Actual OS key restoration, first-run durable integration and UI are not claimed. No live provider/key/configuration was touched.
