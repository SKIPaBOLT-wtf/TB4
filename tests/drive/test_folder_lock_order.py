"""Deterministic SQLite contention; Windows covers SQL only, not a folder server.

Two ordinary preflight readers can both retain SHARED locks in EXCLUSIVE mode.
Pausing the rejected writer models descheduling before its connection closes.
The winner must acquire exclusive ownership before any such preflight read.
"""
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import sys
import threading
import time

from tb4.drive.docs_authority import WriteResult, document_bytes
from tb4.drive.folder_authority import DB, JOURNAL, SCHEMA, FolderConfig, FolderStore, identity
from tb4.exchange_layout import Capacity, empty_document
from folder_fixtures import BINDING, DOMAIN, provision, inventory


def sql_fixture(tmp_path, monkeypatch):
    if sys.platform == "linux":
        return provision(tmp_path)[0]  # Actual native identity/permission checks.
    # Portable SQLite policy regression only. Never qualify Windows as a server.
    root = tmp_path / "synthetic-sql-policy"
    root.mkdir()
    with sqlite3.connect(root / DB, isolation_level=None) as conn:
        conn.execute("PRAGMA locking_mode=EXCLUSIVE")
        conn.execute("PRAGMA journal_mode=PERSIST")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(SCHEMA)
        conn.execute("INSERT INTO authority VALUES (1,?,?,1,?)",
                     (BINDING.root_id, DOMAIN, document_bytes(empty_document(DOMAIN, Capacity(1,1,1,1)))))
        conn.execute("COMMIT")
    conn.close()
    config = FolderConfig(root, BINDING, identity(root), identity(root / DB), identity(root / JOURNAL))
    monkeypatch.setattr(FolderConfig, "verify", lambda self: None)
    return config


def test_preflight_read_contention_does_not_leave_both_cas_without_winner(tmp_path, monkeypatch):
    config = sql_fixture(tmp_path, monkeypatch)
    store = FolderStore(config)
    revision, raw = store.read()
    desired = empty_document(DOMAIN, Capacity(1,1,1,1))
    desired["records"]["global.summary"].update(retention="BUSY", body={"winner": True})
    desired = document_bytes(desired)
    before = inventory(config)
    barrier = threading.Barrier(2)
    original = sqlite3.connect

    class Connection:
        def __init__(self, *args, **kwargs):
            self.conn = original(*args, **kwargs)
        def __getattr__(self, name):
            return getattr(self.conn, name)
        def execute(self, sql, *args):
            try:
                result = self.conn.execute(sql, *args)
            except sqlite3.OperationalError as exc:
                if sql == "BEGIN IMMEDIATE" and exc.sqlite_errorcode == sqlite3.SQLITE_BUSY:
                    # A losing process may be descheduled with its shared lock.
                    time.sleep(0.5)
                raise
            if sql == "SELECT count(*) FROM authority":
                # Old order reaches this read in both connections. Correct order
                # admits just one and the peer is refused before retaining a read.
                try:
                    barrier.wait(timeout=0.4)
                except threading.BrokenBarrierError:
                    pass
            return result

    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", Connection)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: FolderStore(config).compare_replace(revision, desired), range(2)))
    assert results.count(WriteResult.ACCEPTED) == 1, results
    assert set(results) <= {WriteResult.ACCEPTED, WriteResult.REJECTED, WriteResult.UNAVAILABLE}
    assert store.read() == (revision + 1, desired)
    assert store.compare_replace(revision, desired) is WriteResult.REJECTED
    assert inventory(config) == before
