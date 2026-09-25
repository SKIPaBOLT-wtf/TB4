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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap a TB4 tree inside an explicitly selected existing root."
    )
    parser.add_argument("--root-id", required=True, help="Existing backend folder object ID")
    parser.add_argument(
        "--demo-memory",
        action="store_true",
        help="Use deterministic in-memory backend. Real Google Drive wiring is added in later implementation steps.",
    )
    args = parser.parse_args(argv)

    if not args.demo_memory:
        parser.error(
            "no production backend is wired yet; use --demo-memory for protocol/bootstrap validation"
        )

    backend = InMemoryDriveBackend()
    try:
        report = bootstrap_tree(backend, root_id=args.root_id)
    except BootstrapError as exc:
        print(f"TB4 bootstrap failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "root_id": report.root_id,
                "created_count": report.created_count,
                "reused_count": report.reused_count,
                "park_map_generation": report.park_map.map_generation,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
