from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SecurityFinding:
    path: str
    line: int
    code: str
    message: str


_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "PRIVATE_KEY_MATERIAL",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "GITHUB_CLASSIC_TOKEN",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    ),
    (
        "GITHUB_FINE_GRAINED_TOKEN",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    ),
    (
        "GOOGLE_API_KEY",
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ),
    (
        "GOOGLE_OAUTH_ACCESS_TOKEN",
        re.compile(r"\bya29\.[0-9A-Za-z._-]{20,}\b"),
    ),
    (
        "ASSIGNED_SECRET",
        re.compile(
            r"(?i)\b(?:password|passwd|client_secret|refresh_token|access_token)"
            r"\b\s*[:=]\s*[\"']?([A-Za-z0-9._~+/=-]{12,})"
        ),
    ),
)

_BEARER_RE = re.compile(
    r"(?i)(authorization\s*:\s*bearer\s+)([^\s,;]+)"
)
_ASSIGNED_SECRET_RE = re.compile(
    r"(?i)(\b(?:password|passwd|client_secret|refresh_token|access_token)"
    r"\b\s*[:=]\s*[\"']?)([^\s\"',;]+)"
)

_PRIVATE_IPV4_RE = re.compile(
    r"(?<!\d)(?:"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}"
    r")(?!\d)"
)

_PRIVATE_ROOT_RE = re.compile(
    r"(?i)\bTB4_(?:DRIVE_)?ROOT_ID\s*=\s*([A-Za-z0-9_-]{12,})"
)

_TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".jsonl",
    ".ps1",
    ".service",
    ".sh",
    ".txt",
}

_SKIP_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    ".tb4-private",
}


def redact_sensitive_text(text: str) -> str:
    """Remove common credential material from human-readable error text."""

    redacted = _BEARER_RE.sub(r"\1[REDACTED]", text)
    redacted = _ASSIGNED_SECRET_RE.sub(r"\1[REDACTED]", redacted)
    for code, pattern in _SECRET_PATTERNS:
        if code == "ASSIGNED_SECRET":
            continue
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def scan_text(path: str, text: str) -> tuple[SecurityFinding, ...]:
    findings: list[SecurityFinding] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        # Test fixtures may opt out one exact source line. The marker is valid
        # only under tests/ so production/docs/config cannot suppress findings.
        if (
            path.startswith("tests/")
            and "tb4-secret-scan: allow-test-fixture" in line
        ):
            continue

        for code, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    SecurityFinding(
                        path,
                        line_number,
                        code,
                        "high-confidence secret material must not be committed",
                    )
                )

        if _PRIVATE_IPV4_RE.search(line):
            findings.append(
                SecurityFinding(
                    path,
                    line_number,
                    "PRIVATE_IPV4",
                    "private deployment address must not be in the public repository",
                )
            )

        if _PRIVATE_ROOT_RE.search(line):
            findings.append(
                SecurityFinding(
                    path,
                    line_number,
                    "PRIVATE_DRIVE_ROOT",
                    "private TB4 root identifier must not be committed",
                )
            )

    return tuple(findings)


def scan_repository(root: Path) -> tuple[SecurityFinding, ...]:
    root = root.resolve()
    findings: list[SecurityFinding] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in _SKIP_PARTS for part in relative.parts):
            continue
        if path.name not in {"AGENTS.md", "README.md"} and path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(scan_text(relative.as_posix(), text))

    return tuple(findings)
