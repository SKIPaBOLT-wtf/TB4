from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tb4.drive.bootstrap import BootstrapError, bootstrap_tree
from tb4.drive.memory_backend import InMemoryDriveBackend
from tb4.runtime_support import (
    RuntimeConfigurationError,
    RuntimeStartupError,
    build_google_backend,
    load_toml,
    require_string,
    require_table,
)


def _run_bootstrap(backend, root_id: str, *, reveal_root: bool) -> int:
    try:
        report = bootstrap_tree(backend, root_id=root_id)
    except BootstrapError as exc:
        print(f"TB4 bootstrap failed: {exc}", file=sys.stderr)
        return 1

    payload = {
        "created_count": report.created_count,
        "reused_count": report.reused_count,
        "park_map_generation": report.park_map.map_generation,
    }
    if reveal_root:
        payload["root_id"] = report.root_id
    print(json.dumps(payload, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap the canonical TB4 tree inside one explicitly selected existing root."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--demo-memory",
        action="store_true",
        help="bootstrap a deterministic in-memory root without external credentials",
    )
    mode.add_argument(
        "--config",
        type=Path,
        help="private pilot/WATCHDOG/FETCHER TOML containing [drive] values",
    )
    parser.add_argument(
        "--root-id",
        help="demo-only override for the deterministic in-memory root",
    )
    args = parser.parse_args(argv)

    if args.demo_memory:
        backend = InMemoryDriveBackend()
        root_id = args.root_id or backend.root_id
        return _run_bootstrap(backend, root_id, reveal_root=True)

    if args.root_id is not None:
        parser.error("--root-id is only valid with --demo-memory")

    try:
        config = load_toml(args.config)
        drive = require_table(config, "drive")
        root_id = require_string(drive, "root_id")
        backend = build_google_backend(config)
    except (RuntimeConfigurationError, RuntimeStartupError) as exc:
        print(f"TB4 bootstrap setup failed: {exc}", file=sys.stderr)
        return 2

    # Private root IDs are deliberately not echoed in machine-readable output.
    return _run_bootstrap(backend, root_id, reveal_root=False)


if __name__ == "__main__":
    raise SystemExit(main())
