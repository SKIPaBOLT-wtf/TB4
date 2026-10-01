"""Synthetic fixture provisioning only; never a production setup entry point."""
import json
import os
from pathlib import Path
import sqlite3
import sys

import pytest

from tb4.drive.folder_authority import (DB, JOURNAL, SCHEMA, FolderBinding, FolderConfig,
                                       FolderStore, identity, filesystem_type)
from tb4.drive.docs_authority import AuthorityError, document_bytes
from tb4.exchange_layout import Capacity, empty_document

DOMAIN = "10000000-0000-4000-8000-000000000001"
ROOT = "40000000-0000-4000-8000-000000000001"
BINDING = FolderBinding(ROOT, DOMAIN)


def provision(parent, document=None):
    if sys.platform != "linux": pytest.skip("Linux server-local folder mode")
    root = parent / "exchange"
    root.mkdir(mode=0o700)
    try: filesystem_type(root, Path("/proc/self/mountinfo").read_text())
    except AuthorityError:
        if os.environ.get("TB4_REQUIRE_FOLDER_SSH") == "1": pytest.fail("Required server filesystem unsupported")
        pytest.skip("Server requires local ext4/xfs")
    document = document or empty_document(DOMAIN, Capacity(1,1,1,1))
    conn = sqlite3.connect(root/DB, isolation_level=None)
    try:
        conn.execute("PRAGMA page_size=4096")
        conn.execute("PRAGMA locking_mode=EXCLUSIVE")
        conn.execute("PRAGMA journal_mode=PERSIST")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(SCHEMA)
        conn.execute("INSERT INTO authority VALUES (1,?,?,1,?)", (ROOT, DOMAIN, document_bytes(document)))
        conn.execute("COMMIT")
    finally: conn.close()
    for name in (DB,JOURNAL): (root/name).chmod(0o600)
    config = FolderConfig(root, BINDING, identity(root), identity(root/DB), identity(root/JOURNAL))
    value = dict(version=1, root=ROOT, domain=DOMAIN, path=str(root),
                 root_dev=config.root_identity[0], root_ino=config.root_identity[1],
                 db_dev=config.db_identity[0], db_ino=config.db_identity[1],
                 journal_dev=config.journal_identity[0], journal_ino=config.journal_identity[1])
    path = parent/"helper.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)
    return config, path


def inventory(config):
    return {p.name:identity(p) for p in config.root.iterdir()}

