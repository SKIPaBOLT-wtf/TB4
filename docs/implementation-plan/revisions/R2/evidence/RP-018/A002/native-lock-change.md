# RP-018/A002 native lock source

Source5627090c724d95e4bcd97fd352bef7ff9c7e2cae. Changed src/tb4/drive/folder_authority.py, tests/drive/test_folder_lock_order.py and docs/FIXED_FOLDER_AUTHORITY.md. Linux nonblocking flock on the existing independently opened pinned DB inode is acquired before any SQLite connection/read. Descriptor identity/type/owner/mode/link/size and config are checked; nested finally closes lock after SQLite. No additional file/schema/root and no retry. CAS/UNKNOWN/INSPECT unchanged. New tests are Linux native; historical portable Windows SQL repro remains recorded. Actual native tests pending.

Advisory flock requires cooperative qualified helpers. It does not revoke another process or an older helper ignoring the protocol; any deployed helper upgrade remains separately authorized/stopped/version-coordinated. [Linux flock contract](https://man7.org/linux/man-pages/man2/flock.2.html).
