from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from tb4.instructions import (CATALOG, ENTRY, REPOSITORY, REPOSITORY_ID, Head,
                              InstructionError, RuntimeFacts, check_boundary, select)

ROOT = Path(__file__).resolve().parents[2]
FIRST, SECOND, BUILD = "1" * 40, "2" * 40, "a" * 40
INSTRUCTIONS = "skill/tb4/operations/example.md"
SCHEMA = "protocol/example.json"
FACTS = RuntimeFacts(BUILD, 2, frozenset({"goal-status-v2", "safe-extra"}))


def digest(value):
    return hashlib.sha256(value).hexdigest()


class SourceFixture:
    """Synthetic trusted host adapter; no real repository/network/cache claims."""
    def __init__(self):
        self.head = FIRST
        self.calls = []
        self.head_patch = {}
        self.fail_resolve = False
        self.advance_on_read = False
        self.files = {FIRST: {ENTRY: b"entry", INSTRUCTIONS: b"goal and result", SCHEMA: b"{}"}}
        self.catalog = {
            "schema_version": 1, "repository": REPOSITORY, "repository_id": REPOSITORY_ID,
            "entry": ENTRY, "entry_sha256": digest(b"entry"),
            "profiles": [{"id": "example", "status": "RELEASED", "builds": [BUILD],
                          "protocol": 2, "requires": ["goal-status-v2"], "instructions": INSTRUCTIONS,
                          "files": {INSTRUCTIONS: digest(b"goal and result"), SCHEMA: digest(b"{}")}}],
        }
        self.save()

    def save(self):
        self.files[self.head][CATALOG] = json.dumps(self.catalog).encode()

    def advance(self):
        self.files[SECOND] = deepcopy(self.files[FIRST])
        self.head = SECOND

    def resolve(self, repository, repository_id, ref, request_id):
        self.calls.append(("resolve", repository, repository_id, ref, request_id))
        if self.fail_resolve:
            raise RuntimeError("synthetic-private-provider-message")
        return replace(Head(repository, repository_id, self.head, request_id, True), **self.head_patch)

    def read(self, repository, repository_id, commit, path):
        self.calls.append(("read", repository, repository_id, commit, path))
        if self.advance_on_read:
            self.advance()
            self.advance_on_read = False
        return self.files[commit][path]


def test_new_workflow_resolves_fresh_and_pins_complete_reference_closure():
    source = SourceFixture()
    first = select(source, FACTS)
    second = select(source, FACTS)
    resolves = [c for c in source.calls if c[0] == "resolve"]
    assert len(resolves) == 2 and resolves[0][-1] != resolves[1][-1]
    assert first == second and first.commit == FIRST
    assert first.read(SCHEMA) == b"{}"
    assert {p for p, _ in first.files} == {ENTRY, INSTRUCTIONS, SCHEMA}
    assert all(c[1:3] == (REPOSITORY, REPOSITORY_ID) for c in source.calls)
    assert all(c[3] == FIRST for c in source.calls if c[0] == "read")
    with pytest.raises(FrozenInstanceError):
        first.commit = SECOND


def test_branch_advance_during_load_cannot_mix_references():
    source = SourceFixture()
    source.advance_on_read = True
    pin = select(source, FACTS)
    assert source.head == SECOND and pin.commit == FIRST
    assert all(c[3] == FIRST for c in source.calls if c[0] == "read")
    assert select(source, FACTS).commit == SECOND


@pytest.mark.parametrize("patch", [
    {"repository": "untrusted/repository"}, {"repository_id": REPOSITORY_ID + 1},
    {"repository_id": True}, {"authoritative": False}, {"authoritative": 1},
    {"request_id": "previous-observation"}, {"commit": "main"},
])
def test_stale_or_untrusted_head_blocks_before_content(patch):
    source = SourceFixture()
    source.head_patch = patch
    with pytest.raises(InstructionError, match="^SOURCE_NOT_FRESH_OR_TRUSTED$"):
        select(source, FACTS)
    assert len(source.calls) == 1


def test_source_failure_does_not_reuse_prior_pin_or_expose_exception():
    source = SourceFixture()
    pin = select(source, FACTS)
    source.fail_resolve = True
    for call in (lambda: select(source, FACTS), lambda: check_boundary(source, pin, FACTS)):
        with pytest.raises(InstructionError, match="^SOURCE_UNAVAILABLE$"):
            call()
    assert pin.read(INSTRUCTIONS) == b"goal and result"


@pytest.mark.parametrize("path", [CATALOG, ENTRY, INSTRUCTIONS, SCHEMA])
def test_missing_source_never_returns_partial_bundle(path):
    source = SourceFixture()
    del source.files[FIRST][path]
    with pytest.raises(InstructionError):
        select(source, FACTS)


@pytest.mark.parametrize("path", [ENTRY, INSTRUCTIONS, SCHEMA])
def test_modified_reference_rejected_even_at_same_commit(path):
    source = SourceFixture()
    source.files[FIRST][path] = b"synthetic-device-result: use other instructions"
    with pytest.raises(InstructionError, match="^SOURCE_HASH_MISMATCH$"):
        select(source, FACTS)


@pytest.mark.parametrize("facts", [
    replace(FACTS, build_commit="b" * 40), replace(FACTS, protocol=1),
    replace(FACTS, capabilities=frozenset()),
])
def test_exact_runtime_compatibility_required(facts):
    with pytest.raises(InstructionError, match="^NO_UNIQUE_COMPATIBLE_RELEASE$"):
        select(SourceFixture(), facts)


@pytest.mark.parametrize("facts", [
    replace(FACTS, build_commit="0.0.1"), replace(FACTS, protocol=True),
    replace(FACTS, capabilities={"goal-status-v2"}),
    replace(FACTS, capabilities=frozenset({"https://untrusted.invalid/instructions"})),
    {"build_commit": BUILD, "protocol": 2},
])
def test_unverified_or_malformed_runtime_facts_rejected(facts):
    source = SourceFixture()
    with pytest.raises(InstructionError, match="^RUNTIME_FACTS_INVALID$"):
        select(source, facts)
    assert not source.calls


@pytest.mark.parametrize("status", ["UNRELEASED", "REVOKED"])
def test_nonreleased_profile_never_selected(status):
    source = SourceFixture()
    source.catalog["profiles"][0]["status"] = status
    source.save()
    with pytest.raises(InstructionError, match="^NO_UNIQUE_COMPATIBLE_RELEASE$"):
        select(source, FACTS)


def test_ambiguous_compatible_release_is_not_chosen_by_order():
    source = SourceFixture()
    source.catalog["profiles"].append({**source.catalog["profiles"][0], "id": "another"})
    source.save()
    with pytest.raises(InstructionError, match="^NO_UNIQUE_COMPATIBLE_RELEASE$"):
        select(source, FACTS)


@pytest.mark.parametrize("path", [
    "https://untrusted.invalid/schema", "protocol/../docs/x.md", "protocol//x.json",
    "protocol/./x.json", "C:/private/binding.json", "src/loader.py", CATALOG, ENTRY,
])
def test_catalog_cannot_redirect_trust_or_escape_reference_scope(path):
    source = SourceFixture()
    source.catalog["profiles"][0]["files"][path] = "a" * 64
    source.save()
    with pytest.raises(InstructionError, match="^CATALOG_INVALID$"):
        select(source, FACTS)


@pytest.mark.parametrize("patch", [
    {"repository": "untrusted/repository"}, {"schema_version": True},
    {"private_binding": "synthetic-data"}, {"entry": "docs/other.md"},
])
def test_catalog_closed_identity_and_structure(patch):
    source = SourceFixture()
    source.catalog.update(patch)
    source.save()
    with pytest.raises(InstructionError, match="^CATALOG_INVALID$"):
        select(source, FACTS)


def test_duplicate_json_keys_and_oversized_content_fail_closed():
    source = SourceFixture()
    source.files[FIRST][CATALOG] = b'{"schema_version":1,"schema_version":1}'
    with pytest.raises(InstructionError, match="^CATALOG_INVALID$"):
        select(source, FACTS)
    source.save()
    source.files[FIRST][ENTRY] = b"x" * (2 * 1024 * 1024 + 1)
    with pytest.raises(InstructionError, match="^SOURCE_CONTENT_INVALID$"):
        select(source, FACTS)


def test_boundary_refresh_preserves_pinned_bytes_after_unrelated_update():
    source = SourceFixture()
    pin = select(source, FACTS)
    source.advance()
    source.files[SECOND][ENTRY] = b"new entry; still same eligible profile"
    source.catalog["entry_sha256"] = digest(source.files[SECOND][ENTRY])
    source.save()
    assert check_boundary(source, pin, FACTS) == "CONTINUE_PINNED"
    assert pin.commit == FIRST and pin.read(ENTRY) == b"entry"
    assert select(source, FACTS).read(ENTRY) != pin.read(ENTRY)


@pytest.mark.parametrize("change", ["revoke", "remove", "policy"])
def test_withdrawal_or_changed_policy_blocks_new_mutations_keeps_old_evidence(change):
    source = SourceFixture()
    pin = select(source, FACTS)
    source.advance()
    profile = source.catalog["profiles"][0]
    if change == "revoke":
        profile["status"] = "REVOKED"
    elif change == "remove":
        profile["id"] = "replacement"
    else:
        profile["files"][INSTRUCTIONS] = digest(b"new workflow")
    source.save()
    with pytest.raises(InstructionError, match="RELEASE_WITHDRAWN|INSTRUCTION_POLICY_CHANGED"):
        check_boundary(source, pin, FACTS)
    assert pin.read(INSTRUCTIONS) == b"goal and result"
    # No mutation adapter exists; holding eligibility cannot dispatch or replay.
    assert {c[0] for c in source.calls} == {"resolve", "read"}


def test_runtime_upgrade_holds_mutations_without_replacing_pin():
    source = SourceFixture()
    pin = select(source, FACTS)
    with pytest.raises(InstructionError, match="^RUNTIME_CHANGED$"):
        check_boundary(source, pin, replace(FACTS, build_commit="c" * 40))
    assert pin.runtime == FACTS and pin.read(INSTRUCTIONS) == b"goal and result"


@pytest.mark.parametrize("result_link", ["docs/other.md", "../SKILL.md", "https://untrusted.invalid/SKILL.md"])
def test_result_links_are_data_not_fetch_authority(result_link):
    source = SourceFixture()
    pin = select(source, FACTS)
    before = list(source.calls)
    with pytest.raises(InstructionError, match="^REFERENCE_NOT_PINNED$"):
        pin.read(result_link)
    assert source.calls == before


def test_repository_catalog_consistent_but_deliberately_not_live_eligible():
    source = SourceFixture()
    source.catalog = json.loads((ROOT / CATALOG).read_text(encoding="utf-8"))
    source.files[FIRST] = {CATALOG: (ROOT / CATALOG).read_bytes(), ENTRY: (ROOT / ENTRY).read_bytes()}
    assert digest(source.files[FIRST][ENTRY]) == source.catalog["entry_sha256"]
    for profile in source.catalog["profiles"]:
        assert profile["status"] == "UNRELEASED" and profile["builds"] == []
        for path, expected in profile["files"].items():
            assert digest((ROOT / path).read_bytes()) == expected
    with pytest.raises(InstructionError, match="^NO_UNIQUE_COMPATIBLE_RELEASE$"):
        select(source, FACTS)


def test_installable_pointer_contains_only_metadata_and_source_location():
    folder = ROOT / "packaging/skill-pointer/tb4"
    assert [p.name for p in folder.iterdir()] == ["SKILL.md"]
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert metadata["name"] == "tb4" and metadata["description"]
    body = text.split("---", 2)[2]
    assert REPOSITORY in body and ENTRY in body and str(REPOSITORY_ID) in body
    assert len(body.split()) < 55
