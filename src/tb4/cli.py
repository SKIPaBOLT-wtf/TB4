from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
from typing import Callable

from tb4.service_host import ManagedRuntime, ServiceHost


DEFAULT_CONFIG = {
    "watchdog": Path("/etc/tb4/watchdog.toml"),
    "fetcher": Path("/etc/tb4/fetcher.toml"),
}

RUNTIME_FACTORIES = {
    "watchdog": "tb4.watchdog.runtime:create_runtime",
    "fetcher": "tb4.fetcher.runtime:create_runtime",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tb4",
        description="TB4 service entrypoint",
    )
    subparsers = parser.add_subparsers(dest="role", required=True)
    for role in ("watchdog", "fetcher"):
        sub = subparsers.add_parser(role, help=f"run the TB4 {role.upper()} role")
        sub.add_argument(
            "--config",
            type=Path,
            default=DEFAULT_CONFIG[role],
            help=f"external TOML configuration (default: {DEFAULT_CONFIG[role]})",
        )
        sub.add_argument(
            "--check",
            action="store_true",
            help="validate the packaging/config path without starting the runtime",
        )
    return parser


def _resolve_factory(spec: str) -> Callable[[Path], ManagedRuntime]:
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise RuntimeError(f"invalid runtime factory spec {spec!r}")
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute, None)
    if factory is None or not callable(factory):
        raise RuntimeError(f"runtime factory {spec!r} is unavailable")
    return factory


def _validate_config_path(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("service configuration path must be absolute")
    if path.exists() and not path.is_file():
        raise ValueError(f"configuration path is not a file: {path}")


def run_role(role: str, config_path: Path, *, check_only: bool = False) -> int:
    _validate_config_path(config_path)
    if check_only:
        return 0

    override = os.environ.get("TB4_RUNTIME_FACTORY")
    factory_spec = override or RUNTIME_FACTORIES[role]
    factory = _resolve_factory(factory_spec)
    runtime = factory(config_path)
    return ServiceHost(runtime).run()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_role(args.role, args.config, check_only=args.check)
    except (ImportError, AttributeError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"tb4 {args.role}: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
