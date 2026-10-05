"""Fixed single-call server helper. No bootstrap, discovery or command payloads."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import stat
import sys

from .docs_authority import AuthorityError, require
from .folder_authority import FolderBinding, FolderConfig, FolderStore
from .folder_protocol import MAX_WIRE, flat_json, handle


def load_config(path, *, mapping_store=None):
    path = Path(path)
    value = path.lstat()
    require(sys.platform == "linux" and stat.S_ISREG(value.st_mode) and value.st_nlink == 1
            and value.st_uid == os.geteuid() and stat.S_IMODE(value.st_mode) == 0o600, "HELPER_CONFIG")
    with path.open("rb") as stream:
        raw = stream.read(4097)
    require(len(raw) <= 4096, "HELPER_CONFIG")
    config = flat_json(raw)
    require(set(config) == {"version", "root", "domain", "path", "root_dev", "root_ino",
                           "db_dev", "db_ino", "journal_dev", "journal_ino"}
            and type(config["version"]) is int and config["version"] == 1, "HELPER_CONFIG")
    expected=FolderConfig(Path(config["path"]), FolderBinding(config["root"], config["domain"]),
        (config["root_dev"], config["root_ino"]), (config["db_dev"], config["db_ino"]),
        (config["journal_dev"], config["journal_ino"]))
    if mapping_store is None:
        return expected
    from tb4.private_settings import native_settings
    from .folder_mapping import FolderPathMapping
    return FolderPathMapping(native_settings(Path(mapping_store))).select(expected)


def dispatch_mode(command):
    # Treat the server-provided original command as a closed token, never code.
    require(type(command) is str and command in {"tb4-folder-probe-v1", "tb4-folder-v1"},
            "HELPER_COMMAND")
    return command == "tb4-folder-probe-v1"


def main():
    # A dedicated SSH forced command supplies this one fixed path. No client path.
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--mapping-store")  # Explicit protected server-local commissioning pointer.
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--commissioning-probe", action="store_true")
    modes.add_argument("--credential-dispatch", action="store_true")
    args = parser.parse_args()
    if sys.platform != "linux":
        return 2
    signal.signal(signal.SIGALRM, lambda *_: os._exit(2))
    signal.alarm(8)  # Includes config, bounded stdin, recovery, CAS and reply.
    try:
        probe = (dispatch_mode(os.environ.get("SSH_ORIGINAL_COMMAND"))
                 if args.credential_dispatch else args.commissioning_probe)
        config = load_config(args.config,mapping_store=args.mapping_store)
        raw = sys.stdin.buffer.read(MAX_WIRE + 1)
        if probe:
            from .folder_mapping_after_probe import MODE as AFTER_MODE, handle_after_probe
            try:
                after = flat_json(raw).get("mode") == AFTER_MODE
            except Exception:
                after = False
            if after:
                reply = handle_after_probe(config, raw, mapping_store=args.mapping_store)
            else:
                from .folder_probe import handle_probe
                reply = handle_probe(config, raw)
        else:
            reply = handle(FolderStore(config), raw)
        sys.stdout.buffer.write(reply)
        sys.stdout.buffer.flush()
        return 0
    except Exception:
        sys.stdout.buffer.write(b'{"result":"UNKNOWN"}')
        sys.stdout.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

