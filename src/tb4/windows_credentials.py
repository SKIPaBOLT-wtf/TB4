"""Windows identity binding for the shared read-only existing-key policy."""
from dataclasses import dataclass

from .key_policy import ExistingKeyStore, KeyAccessError, Selection


@dataclass(frozen=True, repr=False)
class UserSession:
    sid: str
    session: int
    logon: tuple[int, int]


class WindowsKeyStore(ExistingKeyStore):
    identity_type = UserSession
    reference_prefix = "wk_"

    def principal(self, user):
        return user.sid
