"""Repository-owned instruction selection; no network, runtime mutation or cache.

The host supplies a trusted source adapter and verified nonsecret build facts.
Device/result text can never supply an adapter, repository, ref or instruction.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import secrets
from typing import Protocol

REPOSITORY = "SKIPaBOLT-wtf/TB4"
REPOSITORY_ID = 1387734416
ENTRY = "skill/tb4/SKILL.md"
CATALOG = "skill/tb4/compatibility.json"
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
TOKEN = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
MAX_FILE_BYTES = 2 * 1024 * 1024


class InstructionError(ValueError):
    """Only fixed public error codes leave this module."""


@dataclass(frozen=True)
class RuntimeFacts:
    build_commit: str
    protocol: int
    capabilities: frozenset[str]


@dataclass(frozen=True)
class Head:
    repository: str
    repository_id: int
    commit: str
    request_id: str
    authoritative: bool


class Source(Protocol):
    def resolve(self, repository: str, repository_id: int, ref: str,
                request_id: str) -> Head:
        """Fresh authenticated/HTTPS response; never satisfy from offline cache."""

    def read(self, repository: str, repository_id: int, commit: str,
             path: str) -> bytes:
        """Read this exact repository/commit/path; reject cross-source redirects."""


@dataclass(frozen=True)
class PinnedWorkflow:
    commit: str
    profile: str
    runtime: RuntimeFacts
    policy_digest: str
    instructions: str
    files: tuple[tuple[str, bytes], ...]

    def read(self, path: str) -> bytes:
        for name, content in self.files:
            if name == path:
                return content
        raise InstructionError("REFERENCE_NOT_PINNED")


def _require(condition: bool, code: str = "CATALOG_INVALID") -> None:
    if not condition:
        raise InstructionError(code)


def _keys(value, names) -> None:
    _require(type(value) is dict and set(value) == set(names))


def _matches(pattern, value) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _path(value) -> bool:
    return (type(value) is str and len(value) <= 180
            and re.fullmatch(r"(?:skill/tb4|docs|protocol|config)/[A-Za-z0-9_./-]+\.(?:md|json|yaml|toml)", value) is not None
            and all(part not in {"", ".", ".."} for part in value.split("/"))
            and value not in {ENTRY, CATALOG})


def _facts(facts: RuntimeFacts) -> None:
    _require(type(facts) is RuntimeFacts and _matches(SHA, facts.build_commit)
             and type(facts.protocol) is int and facts.protocol >= 1
             and type(facts.capabilities) is frozenset
             and len(facts.capabilities) <= 64
             and all(_matches(TOKEN, x) for x in facts.capabilities), "RUNTIME_FACTS_INVALID")


def _read(source: Source, commit: str, path: str) -> bytes:
    try:
        content = source.read(REPOSITORY, REPOSITORY_ID, commit, path)
    except Exception:
        raise InstructionError("SOURCE_UNAVAILABLE") from None
    _require(type(content) is bytes and 0 < len(content) <= MAX_FILE_BYTES,
             "SOURCE_CONTENT_INVALID")
    return content


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _catalog(source: Source) -> tuple[str, dict]:
    request = secrets.token_hex(16)
    try:
        head = source.resolve(REPOSITORY, REPOSITORY_ID, "main", request)
    except Exception:
        raise InstructionError("SOURCE_UNAVAILABLE") from None
    _require(type(head) is Head and head.repository == REPOSITORY
             and type(head.repository_id) is int and head.repository_id == REPOSITORY_ID
             and _matches(SHA, head.commit) and head.request_id == request
             and head.authoritative is True, "SOURCE_NOT_FRESH_OR_TRUSTED")
    try:
        catalog = json.loads(_read(source, head.commit, CATALOG), object_pairs_hook=_unique_object)
    except (ValueError, TypeError, RecursionError):
        raise InstructionError("CATALOG_INVALID") from None
    _keys(catalog, {"schema_version", "repository", "repository_id", "entry", "entry_sha256", "profiles"})
    _require(type(catalog["schema_version"]) is int and catalog["schema_version"] == 1
             and catalog["repository"] == REPOSITORY
             and type(catalog["repository_id"]) is int and catalog["repository_id"] == REPOSITORY_ID
             and catalog["entry"] == ENTRY and _matches(DIGEST, catalog["entry_sha256"])
             and type(catalog["profiles"]) is list and 1 <= len(catalog["profiles"]) <= 32)
    ids = set()
    for profile in catalog["profiles"]:
        _keys(profile, {"id", "status", "builds", "protocol", "requires", "instructions", "files"})
        _require(_matches(TOKEN, profile["id"]) and profile["id"] not in ids)
        ids.add(profile["id"])
        _require(type(profile["status"]) is str and profile["status"] in {"RELEASED", "UNRELEASED", "REVOKED"}
                 and type(profile["protocol"]) is int and profile["protocol"] >= 1
                 and type(profile["builds"]) is list and len(profile["builds"]) <= 128
                 and all(_matches(SHA, x) for x in profile["builds"])
                 and len(set(profile["builds"])) == len(profile["builds"])
                 and (profile["status"] != "RELEASED" or bool(profile["builds"]))
                 and type(profile["requires"]) is list and len(profile["requires"]) <= 64
                 and all(_matches(TOKEN, x) for x in profile["requires"])
                 and len(set(profile["requires"])) == len(profile["requires"])
                 and type(profile["files"]) is dict and 1 <= len(profile["files"]) <= 16
                 and all(_path(p) and _matches(DIGEST, h) for p, h in profile["files"].items())
                 and _path(profile["instructions"]) and profile["instructions"] in profile["files"])
    entry = _read(source, head.commit, ENTRY)
    _require(hashlib.sha256(entry).hexdigest() == catalog["entry_sha256"], "SOURCE_HASH_MISMATCH")
    return head.commit, catalog


def _compatible(profile: dict, facts: RuntimeFacts) -> bool:
    return (facts.build_commit in profile["builds"] and facts.protocol == profile["protocol"]
            and set(profile["requires"]) <= facts.capabilities)


def _policy(profile: dict) -> str:
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def select(source: Source, facts: RuntimeFacts) -> PinnedWorkflow:
    """New workflow: resolve fresh main, then read only immutable commit content."""
    _facts(facts)
    commit, catalog = _catalog(source)
    matches = [p for p in catalog["profiles"] if _compatible(p, facts) and p["status"] == "RELEASED"]
    _require(len(matches) == 1, "NO_UNIQUE_COMPATIBLE_RELEASE")
    profile = matches[0]
    files = []
    for path, expected in {ENTRY: catalog["entry_sha256"], **profile["files"]}.items():
        content = _read(source, commit, path)
        _require(hashlib.sha256(content).hexdigest() == expected, "SOURCE_HASH_MISMATCH")
        files.append((path, content))
    return PinnedWorkflow(commit, profile["id"], facts, _policy(profile),
                          profile["instructions"], tuple(files))


def check_boundary(source: Source, pinned: PinnedWorkflow, facts: RuntimeFacts) -> str:
    """Before another mutation, refresh eligibility but never replace the pin.

    On failure preserve the old pin for inspection of already dispatched effects.
    This is not a lease or atomic authorization with a later runtime mutation.
    """
    _require(type(pinned) is PinnedWorkflow, "PIN_INVALID")
    _facts(facts)
    _require(facts == pinned.runtime, "RUNTIME_CHANGED")
    _, catalog = _catalog(source)
    profile = next((p for p in catalog["profiles"] if p["id"] == pinned.profile), None)
    _require(profile is not None and profile["status"] == "RELEASED", "RELEASE_WITHDRAWN")
    _require(_compatible(profile, pinned.runtime) and _policy(profile) == pinned.policy_digest,
             "INSTRUCTION_POLICY_CHANGED")
    return "CONTINUE_PINNED"
