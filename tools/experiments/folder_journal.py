"""RP-018 bounded synthetic SQLite fixed-folder qualification probe.

Not a production backend, deployment command or provider capability attestation.
The caller supplies a new isolated test root. Only children launched here are
interrupted; public results contain synthetic outcomes, not paths or raw errors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


DB = "authority.sqlite"
JOURNAL = DB + "-journal"
SIZE = 384 * 1024


def connect(root, *, exclusive=True, initialize=False):
    if not initialize:
        for name in (DB, JOURNAL):
            path = root / name
            if not path.is_file() or path.is_symlink():
                raise ValueError("FIXED_FILE_MISSING")
    uri = (root / DB).as_uri() + ("?mode=rwc" if initialize else "?mode=rw")
    conn = sqlite3.connect(uri, uri=True, timeout=0.25, isolation_level=None)
    try:
        conn.execute("PRAGMA locking_mode=" + ("EXCLUSIVE" if exclusive else "NORMAL"))
        if conn.execute("PRAGMA journal_mode=PERSIST").fetchone()[0] != "persist":
            raise ValueError("JOURNAL_MODE")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA cache_size=1")
        conn.execute("PRAGMA max_page_count=256")
        return conn
    except Exception:
        conn.close()
        raise


def inventory(root):
    return {p.name:(p.stat().st_dev,p.stat().st_ino) for p in root.iterdir()}


def initialize(root, exclusive):
    root.mkdir(mode=0o700)
    conn = connect(root, exclusive=exclusive, initialize=True)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("CREATE TABLE authority(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, body BLOB NOT NULL)")
        conn.execute("INSERT INTO authority VALUES(1,1,?)", (b"A"*SIZE,))
        conn.execute("COMMIT")
    finally:
        conn.close()


def read(root, exclusive):
    conn = connect(root, exclusive=exclusive)
    try:
        revision, body = conn.execute("SELECT revision,body FROM authority WHERE id=1").fetchone()
        return revision, hashlib.sha256(body).hexdigest(), len(body)
    finally:
        conn.close()


def cas(root, exclusive, expected, marker):
    conn = None
    try:
        conn = connect(root, exclusive=exclusive)
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute("UPDATE authority SET revision=revision+1,body=? WHERE id=1 AND revision=?",
                             (marker.encode()*SIZE, expected)).rowcount
        conn.execute("COMMIT" if count else "ROLLBACK")
        return "ACCEPTED" if count else "REJECTED"
    except sqlite3.OperationalError as exc:
        return "BUSY" if getattr(exc,"sqlite_errorcode",None) in {sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED} else "ERROR"
    finally:
        if conn is not None: conn.close()


def child_args(root, exclusive, action, expected=0, marker="X"):
    return [sys.executable,"-X","utf8","-m","tools.experiments.folder_journal",
            "--root",str(root),"--action",action,"--exclusive",str(int(exclusive)),
            "--expected",str(expected),"--marker",marker]


def worker(args):
    root, exclusive = Path(args.root), bool(args.exclusive)
    if args.action == "cas":
        print(cas(root,exclusive,args.expected,args.marker),flush=True)
        return
    conn = connect(root,exclusive=exclusive)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if args.action == "uncommitted":
            conn.execute("UPDATE authority SET revision=revision+1,body=? WHERE id=1",(b"Z"*SIZE,))
        print("READY",flush=True)
        sys.stdin.buffer.read(1)  # Parent owns bounded lifetime and interruption.
        conn.execute("ROLLBACK")
    finally:
        conn.close()


def kill_owned(child):
    if child.poll() is None: child.kill()
    child.communicate(timeout=10)


def probe(root, *, exclusive=True):
    root = Path(root).absolute()
    initialize(root,exclusive)
    initial = inventory(root)
    if set(initial) != {DB,JOURNAL}:
        raise ValueError("PROVISIONED_INVENTORY")
    first = read(root,exclusive)
    clients = [subprocess.Popen(child_args(root,exclusive,"cas",1,marker),
               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for marker in ("B","C")]
    try:
        outcomes = [p.communicate(timeout=10)[0].decode().strip() for p in clients]
        if any(p.returncode != 0 for p in clients): raise ValueError("CLIENT_EXIT")
    finally:
        for child in clients: kill_owned(child)
    committed = read(root,exclusive)
    before_bytes = (root/DB).read_bytes()
    writer = subprocess.Popen(child_args(root,exclusive,"uncommitted"),
               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    # communicate cannot be used here because EOF intentionally releases worker.
    # A separate readiness reader below is bounded by its Future timeout.
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        if pool.submit(writer.stdout.readline).result(timeout=10).strip() != b"READY":
            raise ValueError("WRITER_NOT_READY")
        changed_before_crash = (root/DB).read_bytes() != before_bytes
        journal_hot_bytes = (root/JOURNAL).stat().st_size
    finally:
        kill_owned(writer)
        pool.shutdown(wait=True)
    restored = read(root,exclusive)
    after_recovery = inventory(root)
    # A deliberate missing-file scenario stays inside the newly owned test root.
    os.rename(root/JOURNAL,root/"held-journal")
    refused = False
    try:
        try: read(root,exclusive)
        except ValueError as exc: refused = str(exc) == "FIXED_FILE_MISSING"
        no_replacement = not (root/JOURNAL).exists()
    finally:
        os.rename(root/"held-journal",root/JOURNAL)
    return dict(schema_version=1,mode="PERSIST_EXCLUSIVE" if exclusive else "PERSIST_NORMAL",
        initial_revision=first[0],concurrent_outcomes=sorted(outcomes),committed_revision=committed[0],
        uncommitted_database_pages_changed=changed_before_crash,journal_bytes_before_crash=journal_hot_bytes,
        reopened_matches_last_committed=restored == committed,
        same_fixed_names=set(after_recovery) == set(initial),same_file_identities=after_recovery == initial,
        missing_journal_rejected=refused,no_missing_journal_recreation=no_replacement,
        final_sizes={name:(root/name).stat().st_size for name in (DB,JOURNAL)},
        actual_power_loss_test=False,remote_ssh_test=False,production_qualified=False)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",required=True)
    parser.add_argument("--action",choices=["probe","cas","uncommitted","lock"],default="probe")
    parser.add_argument("--exclusive",type=int,choices=[0,1],default=1)
    parser.add_argument("--expected",type=int,default=0)
    parser.add_argument("--marker",choices=["B","C","X"],default="X")
    args=parser.parse_args()
    try:
        if args.action == "probe": print(json.dumps(probe(Path(args.root),exclusive=bool(args.exclusive)),sort_keys=True))
        else: worker(args)
        return 0
    except Exception:
        print(json.dumps({"result":"PROBE_UNAVAILABLE"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
