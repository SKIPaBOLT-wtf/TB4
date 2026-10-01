"""Private existing-key metadata, never key material or a public import format.

The caller must store/load this image through installation-bound PrivateSettings.
Native user/session is refreshed on restoration; the original key version,
scope, expiry and revocation are preserved. Capability checks still open/recheck
the exact native key. Restoring an image does not grant READY or execute anything.
"""
from dataclasses import asdict
import copy
import re

from .credential_contract import Binding, CredentialResolver, Purpose, identity
from .key_policy import Selection
from .linux_credentials import LinuxKeyStore
from .windows_credentials import WindowsKeyStore
from .private_settings import SettingsError, encoded, require


def integer(value, low=0, high=10**12):
    return type(value) is int and low <= value <= high


def text(value, pattern):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def purposes(value):
    require(type(value) is list and 1 <= len(value) <= 2
            and all(type(x) is str and x in {p.value for p in Purpose} for x in value)
            and len(set(value)) == len(value), "CREDENTIAL_IMAGE_INVALID")
    return frozenset(Purpose(x) for x in value)


def validate_image(image, installation):
    try:
        require(type(image) is dict and set(image) == {
            "schema_version", "installation_id", "platform", "selections", "bindings"},
            "CREDENTIAL_IMAGE_INVALID")
        require(type(image["schema_version"]) is int and image["schema_version"] == 1
                and identity(installation) and image["installation_id"] == installation
                and type(image["platform"]) is str and image["platform"] in {"WINDOWS","LINUX"},
                "CREDENTIAL_IMAGE_INVALID")
        selections, bindings = image["selections"], image["bindings"]
        require(type(selections) is dict and len(selections) <= 64
                and type(bindings) is dict and len(bindings) <= 128, "CREDENTIAL_IMAGE_INVALID")
        prefix = "wk_" if image["platform"] == "WINDOWS" else "lk_"
        for ref, value in selections.items():
            require(text(ref, prefix + r"[0-9a-f]{32}") and type(value) is dict and set(value) == {
                "path", "principal", "target", "trust", "purposes", "expires", "version",
                "interactive", "revoked"}, "CREDENTIAL_IMAGE_INVALID")
            require(type(value["path"]) is str and 0 < len(value["path"]) <= 32768
                    and "\0" not in value["path"] and identity(value["target"])
                    and text(value["trust"], r"[0-9a-f]{64}")
                    and integer(value["expires"]) and integer(value["version"],1,2**256)
                    and type(value["interactive"]) is bool and type(value["revoked"]) is bool,
                    "CREDENTIAL_IMAGE_INVALID")
            principal = value["principal"]
            require(text(principal, r"S-1-(?:[0-9]{1,15}-){0,14}[0-9]{1,15}")
                    if image["platform"] == "WINDOWS" else integer(principal, 0, 2**32-1),
                    "CREDENTIAL_IMAGE_INVALID")
            require(image["platform"] != "LINUX" or value["interactive"] is False,
                    "CREDENTIAL_IMAGE_INVALID")
            purposes(value["purposes"])
        for handle, value in bindings.items():
            require(text(handle,r"cr_[0-9a-f]{32}") and type(value) is dict and set(value) == {
                "installation_id", "target_id", "target_trust", "store_locator", "purposes",
                "expires_at", "generation", "revoked"}, "CREDENTIAL_IMAGE_INVALID")
            require(value["installation_id"] == installation and type(value["store_locator"]) is str
                    and value["store_locator"] in selections and identity(value["target_id"])
                    and text(value["target_trust"],r"[0-9a-f]{64}")
                    and integer(value["expires_at"]) and integer(value["generation"],1,2**63-1)
                    and type(value["revoked"]) is bool, "CREDENTIAL_IMAGE_INVALID")
            selected = selections[value["store_locator"]]
            require(value["target_id"] == selected["target"] and value["target_trust"] == selected["trust"]
                    and purposes(value["purposes"]) <= purposes(selected["purposes"])
                    and value["expires_at"] <= selected["expires"], "CREDENTIAL_IMAGE_INVALID")
        encoded(image)
        return copy.deepcopy(image)
    except SettingsError:
        raise
    except Exception:
        raise SettingsError("CREDENTIAL_IMAGE_INVALID") from None


def _pair(store, resolver):
    require(type(store) in {WindowsKeyStore,LinuxKeyStore} and type(resolver) is CredentialResolver
            and resolver._store is store and resolver._installation_id == store.installation_id,
            "CREDENTIAL_IMAGE_STORE_MISMATCH")


def preserve_prior_authority(previous, candidate):
    """Retain tombstones; existing references may only gain revocation."""
    if previous is None:
        return
    require(previous["installation_id"] == candidate["installation_id"]
            and previous["platform"] == candidate["platform"], "CREDENTIAL_IMAGE_TRANSITION")
    for section in ("selections", "bindings"):
        for ref, old in previous[section].items():
            new = candidate[section].get(ref)
            require(new is not None and (not old["revoked"] or new["revoked"])
                    and {k:v for k,v in old.items() if k != "revoked"}
                        == {k:v for k,v in new.items() if k != "revoked"},
                    "CREDENTIAL_IMAGE_TRANSITION")


def export_private(store, resolver):
    """Return protected metadata to the private settings transaction, never UI/logs."""
    _pair(store, resolver)
    with resolver._lock, store._lock:
        selections = {}
        for ref, selected in store._selections.items():
            selections[ref] = dict(path=selected.path, principal=store.principal(selected.user),
                target=selected.target, trust=selected.trust, purposes=sorted(p.value for p in selected.purposes),
                expires=selected.expires, version=selected.version, interactive=selected.interactive,
                revoked=selected.revoked)
        bindings = {}
        for handle, binding in resolver._bindings.items():
            value = asdict(binding)
            del value["handle"]
            value["purposes"] = sorted(p.value for p in binding.purposes)
            bindings[handle] = value
        image = dict(schema_version=1, installation_id=store.installation_id,
                     platform="WINDOWS" if type(store) is WindowsKeyStore else "LINUX",
                     selections=selections, bindings=bindings)
        return validate_image(image, store.installation_id)


def restore_private(image, store, resolver):
    """Load into a fresh empty pair only; malformed input cannot partially restore.

    This function is called only with a just-read protected settings image, not a
    JSON file selected as an import. No key is reselected, no handle regenerated,
    and expired/revoked/unavailable selections retain their original status.
    """
    _pair(store, resolver)
    image = validate_image(image, store.installation_id)
    expected = "WINDOWS" if type(store) is WindowsKeyStore else "LINUX"
    require(image["platform"] == expected, "CREDENTIAL_IMAGE_PLATFORM_MISMATCH")
    try:
        user = store._native.identity()
        require(type(user) is store.identity_type, "CREDENTIAL_IMAGE_USER_MISMATCH")
        principal = store.principal(user)
        selections, bindings = {}, {}
        for ref, value in image["selections"].items():
            require(value["principal"] == principal, "CREDENTIAL_IMAGE_USER_MISMATCH")
            selections[ref] = Selection(value["path"], user, value["target"], value["trust"],
                purposes(value["purposes"]), value["expires"], value["version"],
                value["interactive"], value["revoked"])
        for handle, value in image["bindings"].items():
            bindings[handle] = Binding(handle=handle, **{**value, "purposes":purposes(value["purposes"])})
        with resolver._lock, store._lock:
            require(not store._selections and not resolver._bindings, "CREDENTIAL_IMAGE_STORE_NOT_EMPTY")
            require(store._native.identity() == user, "CREDENTIAL_IMAGE_USER_MISMATCH")
            store._selections, resolver._bindings = selections, bindings
    except SettingsError:
        raise
    except Exception:
        raise SettingsError("CREDENTIAL_IMAGE_STORE_UNAVAILABLE") from None
