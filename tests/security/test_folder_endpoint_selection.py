"""Portable pointer/old-profile compatibility; no native availability claim."""
import copy
import os
from pathlib import Path

import pytest

from tb4.commissioning_state import Setup, validated
from tb4.drive.folder_endpoint_selection import selection
from tb4.private_settings import PrivateSettings, SettingsError, encoded
from tb4.reconfiguration_candidate import seed
from tests.security.test_private_settings import MemoryNative


def model():
    native = MemoryNative()
    return native, Setup(PrivateSettings(native), create=True)


def pointer(tmp_path):
    return dict(schema_version=1, reference="fe_"+"a"*32,
        root=str(tmp_path / "synthetic-endpoint-metadata"), binding_digest="b"*64)


def test_closed_pointer_is_copied_and_roundtrips_only_as_private_metadata(tmp_path):
    _, setup = model()
    original = pointer(tmp_path)
    frame = validated({**setup._payload, "folder_endpoint":original})
    assert frame["folder_endpoint"] == original and frame["folder_endpoint"] is not original
    parsed = selection(original)
    original["reference"] = "fe_"+"c"*32
    assert frame["folder_endpoint"] == parsed and frame["folder_endpoint"] is not parsed
    assert not Path(parsed["root"]).exists()


@pytest.mark.parametrize("change", [
    "missing", "extra", "version-bool", "version", "reference", "reference-upper",
    "binding-type", "binding-upper", "binding-short", "root-type", "root-empty",
    "root-relative", "root-parent", "root-nonnormal", "root-control", "root-leading-space",
    "root-trailing-space", "root-url", "root-anchor", "raw-credentials"])
def test_invalid_or_unclosed_pointer_refuses_without_private_value_diagnostics(tmp_path, change):
    value = pointer(tmp_path)
    if change == "missing": del value["binding_digest"]
    if change == "extra": value["ready"] = True
    if change == "version-bool": value["schema_version"] = True
    if change == "version": value["schema_version"] = 2
    if change == "reference": value["reference"] = "cr_"+"a"*32
    if change == "reference-upper": value["reference"] = "fe_"+"A"*32
    if change == "binding-type": value["binding_digest"] = False
    if change == "binding-upper": value["binding_digest"] = "B"*64
    if change == "binding-short": value["binding_digest"] = "b"*63
    if change == "root-type": value["root"] = Path(value["root"])
    if change == "root-empty": value["root"] = ""
    if change == "root-relative": value["root"] = "synthetic-relative"
    if change == "root-parent": value["root"] += os.sep + ".."
    if change == "root-nonnormal": value["root"] += os.sep + "." + os.sep + "child"
    if change == "root-control": value["root"] += "\x00"
    if change == "root-leading-space": value["root"] = " " + value["root"]
    if change == "root-trailing-space": value["root"] += " "
    if change == "root-url": value["root"] = "https://synthetic.invalid/private"
    if change == "root-anchor": value["root"] = Path(value["root"]).anchor
    if change == "raw-credentials": value["password"] = "SYNTHETIC_PRIVATE_CANARY"
    with pytest.raises(SettingsError, match="^FOLDER_ENDPOINT_SELECTION$") as error:
        selection(value)
    assert "SYNTHETIC_PRIVATE_CANARY" not in str(error.value)


def test_old_absent_seed_bytes_and_explicit_null_remain_compatible():
    _, setup = model()
    base = copy.deepcopy(setup._payload)
    assert "folder_endpoint" not in base
    old_seed = {k:copy.deepcopy(base[k]) for k in (
        "schema_version", "installation_id", "setup_nonce", "choices", "operations")}
    for key in ("credential_image", "network_table"):
        if key in base: old_seed[key] = copy.deepcopy(base[key])
    old_seed.update(state="INCOMPLETE", reason="REVALIDATION_REQUIRED")
    assert encoded(seed(base)) == encoded(old_seed) and "folder_endpoint" not in seed(base)
    with_null = validated({**base, "folder_endpoint":None})
    assert with_null["folder_endpoint"] is None and seed(with_null)["folder_endpoint"] is None
    assert setup._payload == base and "folder_endpoint" not in setup.store.read().payload


def test_seed_preserves_pointer_identity_unknown_history_and_full_original_without_alias(tmp_path):
    _, setup = model()
    base = validated({**setup._payload, "folder_endpoint":pointer(tmp_path),
        "operations":{"e"*64:"UNKNOWN"}})
    before = encoded(base)
    staged = seed(base)
    assert staged["folder_endpoint"] == base["folder_endpoint"]
    assert staged["installation_id"] == base["installation_id"] and staged["setup_nonce"] == base["setup_nonce"]
    assert staged["operations"] == base["operations"]
    staged["folder_endpoint"]["reference"] = "fe_"+"c"*32
    staged["operations"]["e"*64] = "CONFIRMED"
    assert encoded(base) == before


def test_pointer_is_not_a_free_choice_or_credential_selection_channel(tmp_path):
    native, setup = model()
    before = copy.deepcopy(native.files)
    with pytest.raises(SettingsError, match="^SETUP_CHOICES_SHAPE$"):
        setup.choose({"folder_endpoint":pointer(tmp_path)})
    assert native.files == before and "folder_endpoint" not in setup.private_choices()


def test_pointer_presence_and_saved_ready_flag_grant_no_native_availability_or_activation(tmp_path):
    _, setup = model()
    value = pointer(tmp_path)
    setup._save({**setup._payload, "folder_endpoint":value,
        "state":"SETTINGS_READY", "reason":"SETTINGS_VALIDATED"})
    reopened = Setup(setup.store)
    assert reopened._payload["folder_endpoint"] == value and not Path(value["root"]).exists()
    status = reopened.status()
    assert not status["settings_validated"] and not status["runtime_active"] and not status["automatic_replay"]


def test_ordinary_stopped_rollback_refuses_a_changed_endpoint_pointer(tmp_path):
    native, setup = model()
    setup._save({**setup._payload, "folder_endpoint":pointer(tmp_path)})
    before = copy.deepcopy(native.files)
    with pytest.raises(SettingsError, match="^SETUP_ROLLBACK_UNSAFE$"):
        setup.rollback_choices(stopped=True)
    assert native.files == before and setup._payload["folder_endpoint"] == pointer(tmp_path)
