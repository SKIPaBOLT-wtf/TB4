from __future__ import annotations

from pathlib import Path

from tb4.security import scan_repository


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = scan_repository(root)
    if not findings:
        print("TB4 public repository security scan: clean")
        return 0

    print("TB4 public repository security scan failed:")
    for finding in findings:
        print(
            f"{finding.path}:{finding.line}: {finding.code}: "
            f"{finding.message}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
