"""Linux64 ext4/XFS existing-key adapter. No external key writes or prompts."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import ctypes
import errno
import hashlib
import os
import platform
import re
import stat
import sys

from .credential_contract import Outcome
from .key_policy import KeyAccessError
from .linux_credentials import UserSession

MAX_KEY_BYTES = 65536


def local_path(path):
    if (type(path) is not str or not path.startswith("/") or
            "\x00" in path or len(path) > 4096):
        raise KeyAccessError(Outcome.DENIED)
    parts = path.split("/")[1:]
    if not 1 <= len(parts) <= 128 or any(not p or p in {".", ".."} for p in parts):
        raise KeyAccessError(Outcome.DENIED)
    return parts


def qualified_mount(fdinfo, mountinfo, magic):
    """Pure bounded parser of kernel descriptor identity, never a path-prefix match."""
    if (type(fdinfo) is not str or type(mountinfo) is not str or
            len(fdinfo) > 8192 or len(mountinfo) > 2 * 1024 * 1024 or type(magic) is not int):
        raise KeyAccessError(Outcome.DENIED)
    ids = [line.split(":", 1)[1].strip() for line in fdinfo.splitlines()
           if line.startswith("mnt_id:")]
    if len(ids) != 1 or not re.fullmatch(r"[1-9][0-9]{0,19}", ids[0]):
        raise KeyAccessError(Outcome.DENIED)
    matches = [line for line in mountinfo.splitlines()
               if line.split(" ", 1)[0] == ids[0]]
    if len(matches) != 1 or matches[0].count(" - ") != 1:
        raise KeyAccessError(Outcome.DENIED)
    left, right = matches[0].split(" - ")
    fields, mounted = left.split(), right.split()
    if (len(fields) < 6 or len(mounted) < 3 or
            not re.fullmatch(r"[0-9]+:[0-9]+", fields[2])):
        raise KeyAccessError(Outcome.DENIED)
    expected = {"ext4": 0xEF53, "xfs": 0x58465342}.get(mounted[0])
    if expected is None or magic != expected:
        raise KeyAccessError(Outcome.DENIED)
    return mounted[0]


def _closed_os(error):
    return KeyAccessError({errno.ENOENT: Outcome.ABSENT, errno.EACCES: Outcome.DENIED,
        errno.EPERM: Outcome.DENIED, errno.ELOOP: Outcome.DENIED,
        errno.ENOTDIR: Outcome.DENIED, errno.EAGAIN: Outcome.LOCKED}.get(
            error.errno, Outcome.STORE_UNAVAILABLE))


class HeldKey:
    """Borrowed sealed memory descriptor, never the selected pathname."""
    __slots__ = ("_native", "_fd", "_source", "_uid", "_info", "_chain", "version")

    def __init__(self, native, fd, source, uid, info, chain, version):
        self._native, self._fd, self._source = native, fd, source
        self._uid, self._info, self._chain = uid, info, chain
        self.version = version

    @property
    def handle(self):
        if self._fd is None:
            raise KeyAccessError(Outcome.DENIED)
        return self._fd

    def recheck(self):
        try:
            self._recheck()
        except OSError as error:
            raise _closed_os(error) from None

    def _recheck(self):
        self._native.recheck_chain(self._chain, self._uid)
        if self._native.file_info(self._source, self._uid) != self._info:
            raise KeyAccessError(Outcome.REVOKED)
        f = self._native.f
        if f.fcntl(self.handle, f.F_GET_SEALS) & self._native.seals != self._native.seals:
            raise KeyAccessError(Outcome.DENIED)


class LinuxKeyNative:
    def __init__(self):
        if (not sys.platform.startswith("linux") or ctypes.sizeof(ctypes.c_long) != 8
                or platform.machine().lower() not in {"x86_64", "aarch64"}):
            raise KeyAccessError()
        try:
            import fcntl
            self.f = fcntl
            self.seals = (fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW |
                          fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
            for name in ("memfd_create", "readv", "getresuid", "getresgid",
                         "O_PATH", "O_NOFOLLOW", "MFD_ALLOW_SEALING"):
                getattr(os, name)
            self._libc = ctypes.CDLL(None, use_errno=True)
            self._libc.fstatfs.argtypes = [ctypes.c_int, ctypes.c_void_p]
            self._libc.fstatfs.restype = ctypes.c_int
        except Exception:
            raise KeyAccessError() from None

    def identity(self):
        try:
            uid, gid = os.getuid(), os.getgid()
            # Includes per-thread filesystem credentials, not just process euid.
            with open("/proc/thread-self/status", "r", encoding="ascii") as source:
                status = source.read(65537)
            if len(status) > 65536:
                raise KeyAccessError()
            fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
            if (os.getresuid() != (uid,) * 3 or os.getresgid() != (gid,) * 3 or
                    tuple(map(int, fields["Uid"].split())) != (uid,) * 4 or
                    tuple(map(int, fields["Gid"].split())) != (gid,) * 4):
                raise KeyAccessError(Outcome.DENIED)
            groups = tuple(sorted(os.getgroups()))
            if tuple(sorted(map(int, fields["Groups"].split()))) != groups:
                raise KeyAccessError(Outcome.DENIED)
            namespaces = tuple(os.readlink("/proc/thread-self/ns/" + n) for n in ("user", "mnt"))
            return UserSession(uid, gid, groups, os.getsid(0), namespaces)
        except KeyAccessError:
            raise
        except Exception:
            raise KeyAccessError() from None

    def _no_acl(self, fd, directory=False):
        names = ["system.posix_acl_access"]
        if directory:
            names.append("system.posix_acl_default")
        for name in names:
            try:
                os.getxattr(fd, name)
            except OSError as error:
                if error.errno != errno.ENODATA:
                    raise KeyAccessError(Outcome.DENIED) from None
            else:
                # Even masked named entries are deliberately unsupported.
                raise KeyAccessError(Outcome.DENIED)

    def directory(self, fd, uid, *, final=False):
        info = os.fstat(fd)
        mode = stat.S_IMODE(info.st_mode)
        sticky_root = info.st_uid == 0 and bool(mode & stat.S_ISVTX)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in {0, uid}
                or (mode & 0o022 and not sticky_root)
                or (final and (info.st_uid != uid or mode & 0o077))):
            raise KeyAccessError(Outcome.DENIED)
        self._no_acl(fd, directory=True)
        return info

    def file_info(self, fd, uid):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid or
                stat.S_IMODE(info.st_mode) not in {0o400, 0o600} or
                info.st_nlink != 1 or not 0 < info.st_size <= MAX_KEY_BYTES):
            raise KeyAccessError(Outcome.DENIED)
        self._no_acl(fd)
        # fstatfs writes the native structure into an oversized aligned buffer;
        # only the first Linux64 long (f_type) is read. No path-based mount guess.
        data = (ctypes.c_long * 64)()
        if self._libc.fstatfs(fd, ctypes.byref(data)) != 0:
            raise KeyAccessError()
        # ext2/ext3 share the ext4 magic. Confirm the same held descriptor's
        # mount ID against the current thread's exact mount table entry.
        with open('/proc/thread-self/fdinfo/' + str(fd), encoding='ascii') as source:
            fdinfo = source.read(8193)
        with open('/proc/thread-self/mountinfo', encoding='utf-8') as source:
            mountinfo = source.read(2 * 1024 * 1024 + 1)
        qualified_mount(fdinfo, mountinfo, data[0])
        return (info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
                info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    def recheck_chain(self, chain, uid):
        for i, (fd, parent, name, identity) in enumerate(chain):
            if i < len(chain) - 1:
                info = self.directory(fd, uid, final=i == len(chain) - 2)
            else:
                info = os.fstat(fd)
            if (info.st_dev, info.st_ino) != identity:
                raise KeyAccessError(Outcome.REVOKED)
            if parent is not None:
                linked = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if (linked.st_dev, linked.st_ino) != identity or stat.S_ISLNK(linked.st_mode):
                    raise KeyAccessError(Outcome.REVOKED)

    @contextmanager
    def open_key(self, path, uid):
        key = None
        try:
            parts = local_path(path)
            if type(uid) is not int or uid != self.identity().uid:
                raise KeyAccessError(Outcome.DENIED)
            with ExitStack() as stack:
                def owned(fd):
                    stack.callback(os.close, fd)
                    return fd
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
                parent = owned(os.open("/", flags))
                root = os.fstat(parent)
                chain = [(parent, None, None, (root.st_dev, root.st_ino))]
                for part in parts[:-1]:
                    self.directory(parent, uid)
                    fd = owned(os.open(part, flags, dir_fd=parent))
                    info = os.fstat(fd)
                    chain.append((fd, parent, part, (info.st_dev, info.st_ino)))
                    parent = fd
                self.directory(parent, uid, final=True)
                # O_PATH checks object type without opening a device or blocking FIFO.
                anchor = owned(os.open(parts[-1], os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                                       dir_fd=parent))
                initial = os.fstat(anchor)
                if not stat.S_ISREG(initial.st_mode):
                    raise KeyAccessError(Outcome.DENIED)
                source = owned(os.open("/proc/self/fd/" + str(anchor),
                                      os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK))
                info = self.file_info(source, uid)
                if info[:2] != (initial.st_dev, initial.st_ino):
                    raise KeyAccessError(Outcome.REVOKED)
                chain.append((source, parent, parts[-1], info[:2]))
                self.f.flock(source, self.f.LOCK_SH | self.f.LOCK_NB)
                data = bytearray(MAX_KEY_BYTES + 1)
                view = memoryview(data)
                try:
                    count = 0
                    while count < len(data):
                        size = os.readv(source, [view[count:]])
                        if size == 0:
                            break
                        count += size
                    if count != info[6] or self.file_info(source, uid) != info:
                        raise KeyAccessError(Outcome.REVOKED)
                    version = hashlib.sha256(repr(info).encode("ascii"))
                    version.update(view[:count])
                    fd = owned(os.memfd_create("tb4-key", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING))
                    os.fchmod(fd, 0o600)
                    written = 0
                    while written < count:
                        size = os.write(fd, view[written:count])
                        if size <= 0:
                            raise KeyAccessError()
                        written += size
                    self.f.fcntl(fd, self.f.F_ADD_SEALS, self.seals)
                    os.lseek(fd, 0, os.SEEK_SET)
                    key = HeldKey(self, fd, source, uid, info, chain,
                                  int.from_bytes(version.digest(), "big") + 1)
                    key.recheck()
                finally:
                    view[:] = b"\x00" * len(data)
                    view.release()
                try:
                    yield key
                finally:
                    key._fd = None
        except KeyAccessError:
            raise
        except OSError as error:
            raise _closed_os(error) from None
        except Exception:
            raise KeyAccessError() from None
        finally:
            if key is not None:
                key._fd = None
