"""Structural private pointer only; no filesystem, native lookup or capability."""
from __future__ import annotations

import copy
from pathlib import Path
import re

from tb4.private_settings import encoded, require

FIELDS = frozenset({"schema_version", "reference", "root", "binding_digest"})


def selection(value):
    require(type(value) is dict and set(value) == FIELDS, "FOLDER_ENDPOINT_SELECTION")
    require(type(value["schema_version"]) is int and value["schema_version"] == 1
        and type(value["reference"]) is str
        and re.fullmatch(r"fe_[0-9a-f]{32}", value["reference"]) is not None
        and type(value["binding_digest"]) is str
        and re.fullmatch(r"[0-9a-f]{64}", value["binding_digest"]) is not None,
        "FOLDER_ENDPOINT_SELECTION")
    root = value["root"]
    require(type(root) is str and 0 < len(root) <= 4096 and root == root.strip()
        and not any(ord(c) < 32 or ord(c) == 127 for c in root), "FOLDER_ENDPOINT_SELECTION")
    path = Path(root)
    require(path.is_absolute() and path.parent != path and ".." not in path.parts
        and not path.drive.startswith("\\\\") and str(path) == root, "FOLDER_ENDPOINT_SELECTION")
    require(len(encoded(value)) <= 32 * 1024, "FOLDER_ENDPOINT_SELECTION")
    return copy.deepcopy(value)
