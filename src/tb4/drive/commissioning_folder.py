"""Explicit Linux folder commissioning; never reachable through ordinary RPC."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import sqlite3
import stat
import sys

from tb4.exchange_layout import empty_document
from .commissioning import Allocation, RAW_LIMIT, digest
from .commissioning_bootstrap import AuthorityHandle
from .docs_authority import AuthorityError, document_bytes, require
from .folder_authority import (DB,JOURNAL,SCHEMA,FolderBinding,FolderConfig,FolderStore,
                               filesystem_type,identity)

ATTR = "user.tb4.commissioning"


class FolderCommissioning:
    mode="FOLDER_SQLITE_V1"

    def __init__(self,root,spec,*,root_identity,llm_authorized):
        require(type(root) is type(Path()) and root.is_absolute() and spec.mode==self.mode
                and llm_authorized is True,"SETUP_ACCESS")
        self.root,self.spec,self.root_identity=root,spec,root_identity
        self.root_id,self.llm_authorized=spec.root_id,llm_authorized
        self.binding=FolderBinding(spec.root_id,spec.domain_id)

    def check_root(self):
        require(sys.platform=="linux","SERVER_PLATFORM_UNSUPPORTED")
        try:
            require(self.root.resolve(strict=True)==self.root and identity(self.root)==self.root_identity,
                    "SETUP_ROOT")
            value=self.root.lstat()
            require(stat.S_ISDIR(value.st_mode) and value.st_uid==os.geteuid()
                    and stat.S_IMODE(value.st_mode)==0o700,"SETUP_ROOT")
            filesystem_type(self.root,Path("/proc/self/mountinfo").read_text())
        except OSError:raise AuthorityError("SETUP_ROOT_UNAVAILABLE") from None

    def _marker(self,key,op):
        from tb4.exchange_layout import encoded
        return encoded(dict(domain=self.spec.domain_id,root=self.root_id,setup=self.spec.setup_id,
                            slot=key,operation=op))

    def _fsync_root(self):
        fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)

    def _config(self):
        return FolderConfig(self.root,self.binding,self.root_identity,identity(self.root/DB),
                            identity(self.root/JOURNAL))

    def _handle(self):
        config=self._config();config.verify()
        require(os.getxattr(self.root/DB,ATTR)==self._marker("authority",self.spec.operation("authority")),
                "SETUP_OBJECT_BINDING")
        FolderStore(config).read()
        return AuthorityHandle(self.root_id,digest([config.root_identity,config.db_identity,
                                                    config.journal_identity,self.spec.fingerprint]),None)

    def inspect_authority(self,spec,known):
        require(spec==self.spec,"SETUP_SPEC")
        self.check_root()
        if not (self.root/DB).exists() or not (self.root/JOURNAL).exists():
            # A partial first creation is preserved. Never initialize/reset it
            # merely because one file or a creator receipt is absent.
            return None
        try:found=self._handle()
        except OSError:raise AuthorityError("SETUP_OBJECT_UNAVAILABLE") from None
        require(known is None or known==found,"BOOTSTRAP_HANDLE_CHANGED")
        return found

    def create_authority(self,spec):
        require(spec==self.spec,"SETUP_SPEC")
        self.check_root()
        require(not any(self.root.iterdir()),"SETUP_ROOT_NOT_EMPTY")
        fd=os.open(self.root/DB,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            os.setxattr(fd,ATTR,self._marker("authority",spec.operation("authority")))
            os.fsync(fd)
        finally:os.close(fd)
        # No CREATE IF NOT EXISTS and no replacement. A failed partial schema is
        # left for exact inspection; only this exclusive fresh file is initialized.
        conn=None
        try:
            conn=sqlite3.connect((self.root/DB).as_uri()+"?mode=rw",uri=True,timeout=.2,isolation_level=None)
            conn.execute("PRAGMA page_size=4096")
            conn.execute("PRAGMA locking_mode=EXCLUSIVE")
            conn.execute("PRAGMA journal_mode=PERSIST")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(SCHEMA)
            conn.execute("INSERT INTO authority VALUES (1,?,?,1,?)",
                         (spec.root_id,spec.domain_id,document_bytes(empty_document(spec.domain_id,spec.capacity))))
            conn.execute("COMMIT")
        finally:
            if conn is not None:conn.close()
        (self.root/JOURNAL).chmod(0o600)
        self._fsync_root()
        return self._handle()

    def authority_store(self,handle):
        require(self.inspect_authority(self.spec,handle)==handle,"BOOTSTRAP_HANDLE")
        return FolderStore(self._config())

    def authority(self,handle):
        # Server-local commissioning still uses the ordinary closed protocol;
        # the creation port is never exposed to normal READ/CAS callers.
        from .folder_protocol import FolderAccess, FolderAuthority, handle as serve
        store=self.authority_store(handle)
        class LocalPort:
            binding=store.binding
            def call(self,raw):return serve(store,raw)
        return FolderAuthority(LocalPort(),self.binding,FolderAccess(self.binding,self.llm_authorized,True))

    def inspect_seed(self,spec,handle):
        require(spec==self.spec,"SETUP_SPEC")
        _,raw=self.authority_store(handle).read()
        if raw==document_bytes(empty_document(spec.domain_id,spec.capacity)):return False
        from .docs_authority import validated
        value=validated(raw,self.binding)
        row=value["records"]["global.commissioning"]
        state=row["body"].get("state") if type(row["body"]) is dict else None
        require(state in {"PREPARING","STORAGE_READY"} and row["body"]==spec.marker(state)
                and row["retention"]=="RETAINED" and row["operation_id"]==spec.setup_id,
                "SETUP_SEED_CONFLICT")
        return True

    def seed(self,spec,handle,raw):
        require(spec==self.spec,"SETUP_SPEC")
        store=self.authority_store(handle)
        revision,current=store.read()
        require(current==document_bytes(empty_document(spec.domain_id,spec.capacity)),"SETUP_NOT_BLANK")
        return store.compare_replace(revision,raw)

    def prepare(self,key,op):
        require(key in self.spec.artifact_keys and op==self.spec.operation(key),"ALLOCATION")
        return Allocation("a"+digest([self.spec.fingerprint,key]),op)

    def create(self,key,allocation):
        require(allocation==self.prepare(key,allocation.operation_id),"ALLOCATION")
        self.check_root()
        fd=os.open(self.root/allocation.object_id,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            os.setxattr(fd,ATTR,self._marker(key,allocation.operation_id))
            os.fsync(fd)
        finally:os.close(fd)
        self._fsync_root()

    def inspect(self,key,allocation):
        expected=self.prepare(key,allocation.operation_id)
        require(type(allocation) is Allocation and allocation.object_id==expected.object_id,"ALLOCATION")
        self.check_root()
        path=self.root/allocation.object_id
        try:
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        except FileNotFoundError:return None
        try:
            value=os.fstat(fd)
            require(stat.S_ISREG(value.st_mode) and value.st_uid==os.geteuid() and value.st_nlink==1
                    and stat.S_IMODE(value.st_mode)==0o600 and value.st_size<=RAW_LIMIT,
                    "SETUP_OBJECT")
            require(os.getxattr(fd,ATTR)==self._marker(key,allocation.operation_id),"SETUP_OBJECT_BINDING")
            seal=digest([self.root_identity,(value.st_dev,value.st_ino),self.spec.fingerprint,key])
            require(allocation.seal is None or allocation.seal==seal,"ALLOCATION_IDENTITY")
            return replace(allocation,seal=seal)
        except OSError:raise AuthorityError("SETUP_OBJECT_UNAVAILABLE") from None
        finally:os.close(fd)
