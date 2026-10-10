"""Exact native first-run proof and existing normal authority composition.

Construction supplies no credential, role, readiness or activation grant.
Each normal request uses the existing fresh protected NativeFolderConnection.
"""
from .commissioning_bootstrap import AuthorityHandle
from .docs_authority import AuthorityError, require
from .folder_connection import NativeFolderConnection
from .folder_first_run import RemoteFolderCommissioning
from .folder_protocol import FolderAccess


class NativeFolderCommissioning:
    mode = "FOLDER_SQLITE_V1"

    def __init__(self, connection, access):
        require(type(connection) is NativeFolderConnection and type(access) is FolderAccess,
                "FOLDER_RUNTIME_CONTEXT")
        connection._current()
        self._connection, self._access = connection, access
        self._proof = RemoteFolderCommissioning(connection.probe(access))
        self.spec, self.root_id = connection.spec, connection.spec.root_id
        self._pins = (connection, access, self._proof, self.spec, self.root_id, self.mode)

    def _current(self):
        require(type(self) is NativeFolderCommissioning
            and (self._connection, self._access, self._proof,
                 self.spec, self.root_id, self.mode) == self._pins
            and self.spec == self._connection.spec
            and type(self._proof) is RemoteFolderCommissioning,
                "FOLDER_RUNTIME_CHANGED")
        self._connection._current()

    def verify(self, record):
        try:
            self._current()
            return RemoteFolderCommissioning.verify(self._proof, record)
        except Exception:
            raise AuthorityError("REMOTE_STORAGE_UNAVAILABLE") from None

    def authority(self, handle):
        self._current()
        require(type(handle) is AuthorityHandle and handle == self._connection.authority,
                "FOLDER_RUNTIME_AUTHORITY")
        return self._connection.authority_client(self._access)
