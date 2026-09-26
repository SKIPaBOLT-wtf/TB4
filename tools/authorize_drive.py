from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tb4.drive.google_client import GoogleAuthConfig, build_google_drive_client
from tb4.runtime_support import (
    RuntimeConfigurationError,
    load_toml,
    require_string,
    require_table,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Perform explicit local Google OAuth authorization for TB4."
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="private TOML containing [drive] client_secrets_path and token_path",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not ask the OAuth helper to open a browser automatically",
    )
    args = parser.parse_args(argv)

    try:
        config = load_toml(args.config)
        drive = require_table(config, "drive")
        auth = GoogleAuthConfig(
            Path(require_string(drive, "client_secrets_path")),
            Path(require_string(drive, "token_path")),
            allow_interactive=True,
            open_browser=not args.no_browser,
        )
    except RuntimeConfigurationError as exc:
        print(f"TB4 authorization setup failed: {exc}", file=sys.stderr)
        return 2

    report = build_google_drive_client(auth)
    if not report.ready:
        print(
            f"TB4 authorization failed: {report.outcome.value}: {report.message or ''}".rstrip(),
            file=sys.stderr,
        )
        return 1

    print(
        "TB4 Google Drive authorization ready"
        + ("; local token updated" if report.token_written else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
