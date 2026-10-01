# RP-018/A002 native Linux lock validation

Source5627090c724d95e4bcd97fd352bef7ff9c7e2cae; INTENT0033; local exec18143 completed. A single isolated WSL Linux process prepared a fresh ext4 test directory and private venv from the exact public Git archive. No system package/network/live TB4 change. Python3.12.3, SQLite3.45.1, pytest9.1.1.

Command: `python -X utf8 -m pytest tests/drive/test_folder_lock_order.py tests/drive/test_folder_store.py tests/drive/test_folder_protocol.py tests/drive/test_folder_commissioning.py tests/drive/test_folder_ssh.py --basetemp <fresh-task-temp> -ra`.
Observed71passed3skipped12.02s, pytest0/WSL0. The3 skipped cases are test_folder_ssh.py116/130/147: local OpenSSH prerequisite absent; required hosted CI installs it and must execute these cases.

The deterministic originally failing preflight interleaving now admits exactly one CAS writer; peer unavailable/stale rejection remain separate, final revision/body and fixed inode inventory match. Read connection excludes contenders then releases without mutation. Original real subprocess killed-writer/hot-journal test restores last committed content and same DB/journal identities, thereby exercising kernel-lock release after owned process death. Existing root/domain/schema/access/no-replay/protocol and folder commissioning cases pass. No copied-host identity, actual endpoint or credentials were used.

Prior portable Windows failure and failed empty-SQLite-transaction fix remain immutable. New server-lock tests execute only on qualified Linux; Windows remains a client. All helpers must cooperate with the lock; no live migration or instantaneous revocation of an older helper is claimed. Full hosted SSH/platform/package and source/privacy/history review remain required.
