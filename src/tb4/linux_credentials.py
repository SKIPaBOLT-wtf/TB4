"""Linux existing-key selection; no interactive store/agent fallback."""
from dataclasses import dataclass

from .credential_contract import Outcome
from .key_policy import ExistingKeyStore, KeyAccessError


@dataclass(frozen=True, repr=False)
class UserSession:
    uid: int
    gid: int
    groups: tuple[int, ...]
    session: int
    namespaces: tuple[str, str]


class LinuxKeyStore(ExistingKeyStore):
    identity_type = UserSession
    reference_prefix = "lk_"

    def principal(self, user):
        return user.uid

    def select(self, *, path, target_id, target_trust, purposes, expires_at,
               access_mode, launch_mode, owner_authorized):
        # Existing-file access requires no keyring daemon, display or unlock UI.
        # No SSH_AUTH_SOCK, desktop environment or home-directory guessing.
        if (type(access_mode) is not str or access_mode != "existing_key" or
                type(launch_mode) is not str or launch_mode not in {"desktop", "headless"}):
            raise KeyAccessError(Outcome.STORE_UNAVAILABLE)
        return super().select(path=path, target_id=target_id, target_trust=target_trust,
                              purposes=purposes, expires_at=expires_at,
                              interactive_required=False, owner_authorized=owner_authorized)
