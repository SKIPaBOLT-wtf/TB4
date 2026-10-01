"""Unreleased fixed-folder authority. Server-local ext4/xfs only, never a sync cache.

Provisioning is separate. Ordinary requests open two existing pinned files and
never discover/create/rename/delete a root. The private directory, helper and
configuration must be controlled by the same trusted OS account. This is not a
sandbox against that account, storage administrators or dishonest hardware.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
from uuid import UUID

from tb4.exchange_layout import MAX_DOCUMENT_BYTES, MAX_GENERATION
from .docs_authority import AuthorityError, WriteResult, document_bytes, require, validated

DB = "authority.sqlite"
JOURNAL = DB + "-journal"
MAX_FILE = 4 * 1024 * 1024
SCHEMA = ("CREATE TABLE authority (id INTEGER PRIMARY KEY CHECK (id = 1), "
          "root TEXT NOT NULL, domain TEXT NOT NULL, revision INTEGER NOT NULL, body BLOB NOT NULL)")


@dataclass(frozen=True, repr=False)
class FolderBinding:
    root_id: str
    domain_id: str

    def __post_init__(self):
        for value in (self.root_id, self.domain_id):
            try:
                require(type(value) is str and str(UUID(value)) == value, "FOLDER_BINDING")
            except (ValueError, AttributeError, TypeError):
                raise AuthorityError("FOLDER_BINDING") from None


def identity(path):
    value = path.lstat()
    return value.st_dev, value.st_ino


def filesystem_type(root, mountinfo):
    """Most specific mount, including nested/bind mounts; no path text in errors."""
    selected, depth = None, -1
    for line in mountinfo.splitlines():
        parts = line.split()
        try:
            split = parts.index("-")
            mount = Path(re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), parts[4]))
            if root == mount or mount in root.parents:
                if len(mount.parts) >= depth:
                    selected, depth = parts[split + 1], len(mount.parts)
        except (ValueError, IndexError):
            raise AuthorityError("FILESYSTEM_UNQUALIFIED") from None
    require(selected in {"ext4", "xfs"}, "FILESYSTEM_UNQUALIFIED")
    return selected


@dataclass(frozen=True, repr=False)
class FolderConfig:
    root: Path
    binding: FolderBinding
    # Installed locally by explicit commissioning; never received in RPC.
    root_identity: tuple[int, int]
    db_identity: tuple[int, int]
    journal_identity: tuple[int, int]

    def __post_init__(self):
        require(type(self.root) is type(Path()) and self.root.is_absolute()
                and isinstance(self.binding, FolderBinding), "FOLDER_CONFIG")
        for value in (self.root_identity, self.db_identity, self.journal_identity):
            require(type(value) is tuple and len(value) == 2
                    and all(type(v) is int and v >= 0 for v in value), "FOLDER_CONFIG")

    def verify(self):
        require(sys.platform == "linux", "SERVER_PLATFORM_UNSUPPORTED")
        try:
            require(self.root.resolve(strict=True) == self.root, "ROOT_ALIAS")
            filesystem_type(self.root, Path("/proc/self/mountinfo").read_text())
            for path, expected, directory in (
                (self.root, self.root_identity, True),
                (self.root / DB, self.db_identity, False),
                (self.root / JOURNAL, self.journal_identity, False),
            ):
                value = path.lstat()
                require((value.st_dev, value.st_ino) == expected, "FIXED_IDENTITY")
                require(value.st_uid == os.geteuid() and stat.S_IMODE(value.st_mode)
                        == (0o700 if directory else 0o600), "PRIVATE_PERMISSIONS")
                require(stat.S_ISDIR(value.st_mode) if directory else
                        stat.S_ISREG(value.st_mode) and value.st_nlink == 1, "FIXED_OBJECT_TYPE")
                if not directory:
                    require(value.st_size <= MAX_FILE, "FIXED_OBJECT_SIZE")
            # A foreign sidecar is not removed or adopted. Never enable WAL.
            require(not any((self.root / (DB + suffix)).exists()
                            for suffix in ("-wal", "-shm")), "FOREIGN_JOURNAL")
        except OSError:
            raise AuthorityError("FOLDER_UNAVAILABLE") from None


class FolderStore:
    """Fixed helper's server-side primitive; all clients share this one authority."""
    def __init__(self, config):
        require(isinstance(config, FolderConfig), "FOLDER_CONFIG")
        self.config, self.binding = config, config.binding

    @contextmanager
    def connection(self):
        self.config.verify()
        conn = lock = None
        try:
            # Every qualified Linux helper locks the existing database inode
            # before SQLite can retain preflight read locks. No extra file and
            # no retry: a competing helper is unavailable before CAS starts.
            import fcntl
            lock = os.open(self.config.root / DB, os.O_RDONLY | os.O_NOFOLLOW |
                           os.O_CLOEXEC | os.O_NONBLOCK)
            info = os.fstat(lock)
            require((info.st_dev, info.st_ino) == self.config.db_identity
                    and stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                    and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
                    and info.st_size <= MAX_FILE, "FIXED_IDENTITY")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.config.verify()
            conn = sqlite3.connect((self.config.root / DB).as_uri() + "?mode=rw",
                                   uri=True, timeout=0.2, isolation_level=None)
            conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_DOCUMENT_BYTES + 4096)
            conn.execute("PRAGMA trusted_schema=OFF")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA locking_mode=EXCLUSIVE")
            require(conn.execute("PRAGMA journal_mode=PERSIST").fetchone() == ("persist",), "JOURNAL_MODE")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA cache_size=1")
            require(conn.execute("PRAGMA page_size").fetchone() == (4096,), "DATABASE_FORMAT")
            require(conn.execute("PRAGMA max_page_count=512").fetchone() == (512,), "DATABASE_CAPACITY")
            require(conn.execute("SELECT type,name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'")
                    .fetchall() == [("table", "authority", SCHEMA)], "DATABASE_SCHEMA")
            require(conn.execute("SELECT count(*) FROM authority").fetchone() == (1,), "DATABASE_ROWS")
            self.config.verify()
            yield conn
        finally:
            try:
                if conn is not None:
                    conn.close()  # Roll back; PERSIST keeps the same journal.
            finally:
                if lock is not None:
                    os.close(lock)

    def _row(self, conn):
        row = conn.execute("SELECT root,domain,revision,body FROM authority WHERE id=1").fetchone()
        require(row is not None and row[:2] == (self.binding.root_id, self.binding.domain_id), "FOLDER_BINDING")
        revision, raw = row[2:]
        require(type(revision) is int and 1 <= revision <= MAX_GENERATION, "REVISION_INVALID")
        require(type(raw) is bytes, "CONTROL_INVALID")
        validated(raw, self.binding)
        return revision, raw

    def read(self):
        try:
            with self.connection() as conn:
                result = self._row(conn)
                self.config.verify()
                return result
        except (OSError, sqlite3.Error):
            raise AuthorityError("READ_UNAVAILABLE") from None

    def compare_replace(self, expected, raw):
        require(type(expected) is int and 1 <= expected < MAX_GENERATION, "REVISION_INVALID")
        desired = validated(raw, self.binding)
        begun = False
        try:
            with self.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                begun = True
                revision, prior = self._row(conn)
                old = validated(prior, self.binding)
                require(all(old[k] == desired[k] for k in old if k != "records"), "LAYOUT_CHANGED")
                if revision != expected:
                    return WriteResult.REJECTED
                self.config.verify()
                conn.execute("UPDATE authority SET revision=revision+1,body=? WHERE id=1 AND revision=?",
                             (raw, expected))
                conn.execute("COMMIT")
                self.config.verify()
                return WriteResult.ACCEPTED  # Client must still read back the intended transition.
        except (OSError, sqlite3.Error, AuthorityError):
            return WriteResult.UNKNOWN if begun else WriteResult.UNAVAILABLE
