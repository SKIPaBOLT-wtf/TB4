"""Selected Linux syscall adapter; ordinary helper never exposes this port."""
import ctypes
import os
import stat
import sys

from tb4.configuration_contract import require
from .folder_mapping import _parent
from .folder_authority import identity


class NativeFolderRename:
    def __init__(self):
        require(sys.platform=="linux","SERVER_PLATFORM_UNSUPPORTED")
        self.lib=ctypes.CDLL(None,use_errno=True)
        require(hasattr(self.lib,"renameat2"),"FOLDER_RENAME_UNSUPPORTED")
        self.lib.renameat2.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
        self.lib.renameat2.restype=ctypes.c_int

    def _call(self,source_fd,source_name,target_fd,target_name):
        # Linux RENAME_NOREPLACE=1. Never fall back to replacing rename/copy.
        return self.lib.renameat2(source_fd,os.fsencode(source_name),target_fd,os.fsencode(target_name),1)

    def run(self,source,target,source_parent,target_parent,root_identity):
        _parent(source,source_parent);_parent(target,target_parent)
        require(identity(source)==tuple(root_identity) and not os.path.lexists(target),
                "FOLDER_RENAME_CHANGED")
        opened=[]
        try:
            for path,expected in ((source.parent,source_parent),(target.parent,target_parent)):
                fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
                opened.append(fd);info=os.fstat(fd)
                require((info.st_dev,info.st_ino)==tuple(expected) and info.st_uid==os.geteuid()
                        and stat.S_IMODE(info.st_mode)==0o700,"FOLDER_RENAME_PARENT")
            _parent(source,source_parent);_parent(target,target_parent)
            require(self._call(opened[0],source.name,opened[1],target.name)==0,
                    "FOLDER_RENAME_UNCONFIRMED")
            for fd in opened:os.fsync(fd)
        finally:
            for fd in opened:os.close(fd)
