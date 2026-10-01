"""Private setup checkpoint with exclusive per-installation OS locking.

The supplied protection verifier must qualify the dedicated local directory and
its OS ACL/identity. The journal proves locking/atomic replacement/readback, not
credential-store qualification or physical power-loss behavior. No shared root,
network path discovery or automatic directory creation occurs here.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
import hashlib
import os
from pathlib import Path
import stat
import sys

from tb4.exchange_layout import encoded
from tb4.security_contract import parse_control
from .docs_authority import AuthorityError, require


class JournalSection:
    """Two bounded sections share the same already-held installation lock."""
    def __init__(self,journal,name):
        require(name in {"bootstrap","commissioning"},"SETUP_JOURNAL_SECTION")
        self.journal,self.name=journal,name

    @property
    def installation_id(self):return self.journal.installation_id

    @property
    def setup_id(self):return self.journal.setup_id

    @property
    def protected(self):return self.journal.protected

    @property
    def locked(self):return self.journal.locked

    def read(self):
        state=self.journal.read()
        require(state is None or type(state) is dict and set(state)<={"bootstrap","commissioning"},
                "SETUP_JOURNAL_SECTION")
        return None if state is None else state.get(self.name)

    def save(self,payload):
        state=self.journal.read() or {}
        require(type(state) is dict and set(state)<={"bootstrap","commissioning"},"SETUP_JOURNAL_SECTION")
        self.journal.save({**state,self.name:payload})


class SetupJournal(AbstractContextManager):
    def __init__(self, root, *, installation_id, setup_id, verify_protection):
        from .commissioning import uuid
        require(isinstance(root,Path) and root.is_absolute() and uuid(installation_id)
                and type(setup_id) is str and len(setup_id)==64
                and all(c in "0123456789abcdef" for c in setup_id)
                and callable(verify_protection), "SETUP_JOURNAL")
        self.root,self.installation_id,self.setup_id=root,installation_id,setup_id
        self._verify=verify_protection
        self.protected=self.locked=False
        self._lock=None
        self.path=root/(setup_id+".json")
        self.temp=root/(setup_id+".pending")
        self.lock_path=root/(setup_id+".lock")

    def _check(self):
        require(self.root.resolve(strict=True)==self.root and self._verify(self.root) is True,
                "SETUP_JOURNAL_PROTECTION")
        self.protected=True

    def _regular(self,path):
        if path.exists() or path.is_symlink():
            value=path.lstat()
            require(stat.S_ISREG(value.st_mode) and value.st_nlink==1, "SETUP_JOURNAL_OBJECT")
            if os.name=="posix":
                require(value.st_uid==os.geteuid() and stat.S_IMODE(value.st_mode)==0o600,
                        "SETUP_JOURNAL_OBJECT")

    def __enter__(self):
        require(not self.locked and self._lock is None,"SETUP_JOURNAL_LOCK")
        try:
            self._check();self._regular(self.lock_path)
            fd=os.open(self.lock_path,os.O_RDWR|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
            self._lock=os.fdopen(fd,"r+b",buffering=0)
            if sys.platform=="win32":
                import msvcrt
                # Locking one byte beyond EOF is supported; no pre-lock write.
                self._lock.seek(0);msvcrt.locking(self._lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self._lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.locked=True
            self._regular(self.path);self._regular(self.temp)
            return self
        except Exception:
            if self._lock:self._lock.close()
            self._lock=None;self.locked=False
            raise AuthorityError("SETUP_JOURNAL_LOCK") from None

    def __exit__(self,*_):
        if self._lock is not None:
            self._lock.close()  # Closing releases both OS lock implementations.
        self._lock=None;self.locked=False;self.protected=False
        return False

    def read(self):
        require(self.locked,"SETUP_JOURNAL_LOCK")
        try:
            self._check();self._regular(self.path)
            if not self.path.exists():return None
            with self.path.open("rb") as stream:raw=stream.read(512*1024+1)
            frame=parse_control(raw)
            require(type(frame) is dict and set(frame)=={"installation","setup","payload","sha256"}
                    and frame["installation"]==self.installation_id and frame["setup"]==self.setup_id
                    and frame["sha256"]==hashlib.sha256(encoded(frame["payload"])).hexdigest(),
                    "SETUP_JOURNAL_BINDING")
            return frame["payload"]
        except Exception:
            raise AuthorityError("SETUP_JOURNAL_UNAVAILABLE") from None

    def save(self,payload):
        require(self.locked and type(payload) is dict,"SETUP_JOURNAL_LOCK")
        try:
            self._check();self._regular(self.path);self._regular(self.temp)
            frame=dict(installation=self.installation_id,setup=self.setup_id,payload=payload,
                       sha256=hashlib.sha256(encoded(payload)).hexdigest())
            raw=encoded(frame)
            require(len(raw)<=512*1024,"SETUP_JOURNAL_SIZE")
            parse_control(raw)
            # The fixed .pending file is this journal's nonauthoritative staging
            # object under its exclusive lock. A crash may leave partial bytes;
            # replacing those never deletes/rewrites the confirmed checkpoint.
            fd=os.open(self.temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|getattr(os,"O_NOFOLLOW",0),0o600)
            with os.fdopen(fd,"wb") as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.replace(self.temp,self.path)
            if os.name=="posix":
                fd=os.open(self.root,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
                try:os.fsync(fd)
                finally:os.close(fd)
            require(encoded(self.read())==encoded(payload),"SETUP_JOURNAL_READBACK")
        except Exception:
            raise AuthorityError("SETUP_JOURNAL_UNAVAILABLE") from None

