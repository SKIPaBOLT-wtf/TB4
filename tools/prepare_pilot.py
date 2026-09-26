from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tb4.pilot.config_builder import PilotConfigError, load_and_build, write_private_configs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate private WATCHDOG and FETCHER configs from one TB4 pilot config."
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        generated = load_and_build(args.config)
        write_private_configs(generated, args.output_dir)
    except PilotConfigError as exc:
        print(f"TB4 pilot config generation failed: {exc}", file=sys.stderr)
        return 2

    # Deliberately do not echo deployment paths or private values.
    print("TB4 private WATCHDOG/FETCHER configuration generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
