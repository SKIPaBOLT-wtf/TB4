"""Linux64 protected R2 settings directory. No chmod/chown of existing data."""
from contextlib import ExitStack, contextmanager
import hashlib
import os
import re
import stat
from pathlib import Path

from .linux_key_native import LinuxKeyNative, local_path
from .private_settings import MAX_BYTES, SettingsError, require


class LinuxSettingsNative:
    def __init__(self, root, *, create=False):
        require(isinstance(root, Path) and root.is_absolute(), "SETTINGS_PATH_INVALID")
        self.root = root
        self.api = LinuxKeyNative()
        self.user = self.api.identity()
        # Stable private host binding, not a public device alias or a secret.
        with open("/etc/machine-id", "r", encoding="ascii") as source:
            machine = source.read(129).strip()
        require(re.fullmatch("[0-9a-f]{32}", machine) is not None, "SETTINGS_HOST_UNAVAILABLE")
        self.host = hashlib.sha256(machine.encode("ascii")).hexdigest()
        if create:
            self._create()

    def _walk_parent(self, stack):
        parts = local_path(str(self.root))
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        fd = os.open("/", flags)
        stack.callback(os.close, fd)
        chain = [(fd, None, None)]
        for part in parts[:-1]:
            self.api.directory(fd, self.user.uid)
            child = os.open(part, flags, dir_fd=fd)
            stack.callback(os.close, child)
            chain.append((child, fd, part))
            fd = child
        self.api.directory(fd, self.user.uid)
        return fd, parts[-1], chain

    def _create(self):
        with ExitStack() as stack:
            parent, name, _ = self._walk_parent(stack)
            self.api.filesystem(parent)
            # mkdir is exclusive. Existing directory is not an authorization to
            # rewrite its permissions; caller must reopen with create=False.
            os.mkdir(name, mode=0o700, dir_fd=parent)

    @contextmanager
    def locked(self):
        try:
            with ExitStack() as stack:
                require(self.api.identity() == self.user, "SETTINGS_USER_CHANGED")
                parent, name, chain = self._walk_parent(stack)
                root_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                                  os.O_CLOEXEC, dir_fd=parent)
                stack.callback(os.close, root_fd)
                root_info = self.api.directory(root_fd, self.user.uid, final=True)
                self.api.filesystem(root_fd)
                try:
                    lock_fd = os.open("settings.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL |
                                      os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=root_fd)
                except FileExistsError:
                    lock_fd = self._open_existing(root_fd, "settings.lock", write=True)
                stack.callback(os.close, lock_fd)
                self._regular(lock_fd)
                try:
                    self.api.f.flock(lock_fd, self.api.f.LOCK_EX | self.api.f.LOCK_NB)
                except OSError:
                    raise SettingsError("SETTINGS_BUSY") from None
                port = LinuxSettingsPort(self, root_fd, parent, name, chain,
                                          (root_info.st_dev, root_info.st_ino))
                port.check()
                yield port
        except SettingsError:
            raise
        except Exception:
            raise SettingsError("SETTINGS_STORE_UNAVAILABLE") from None

    def _regular(self, fd):
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == self.user.uid and
                stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
                and info.st_size <= MAX_BYTES, "SETTINGS_FILE_PROTECTION")
        self.api._no_acl(fd)
        return info

    def _open_existing(self, root_fd, name, *, write=False):
        anchor = os.open(name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=root_fd)
        try:
            info = os.fstat(anchor)
            require(stat.S_ISREG(info.st_mode), "SETTINGS_FILE_PROTECTION")
            fd = os.open('/proc/self/fd/' + str(anchor),
                         (os.O_RDWR if write else os.O_RDONLY) | os.O_CLOEXEC | os.O_NONBLOCK)
            try:
                opened = self._regular(fd)
                require((info.st_dev, info.st_ino) == (opened.st_dev, opened.st_ino),
                        "SETTINGS_CHANGED_RELOAD_REQUIRED")
                return fd
            except BaseException:
                os.close(fd)
                raise
        finally:
            os.close(anchor)


class LinuxSettingsPort:
    def __init__(self, native, root_fd, parent, name, chain, identity):
        self.native, self.fd, self.parent, self.name = native, root_fd, parent, name
        self.chain, self.identity = chain, identity
        self.binding = dict(platform="LINUX", host=native.host,
                            principal=[native.user.uid, native.user.gid],
                            directory=list(identity))

    def check(self):
        n = self.native
        require(n.api.identity() == n.user, "SETTINGS_USER_CHANGED")
        for fd, parent, name in self.chain:
            info = n.api.directory(fd, n.user.uid)
            if parent is not None:
                linked = os.stat(name, dir_fd=parent, follow_symlinks=False)
                require((info.st_dev, info.st_ino) == (linked.st_dev, linked.st_ino)
                        and not stat.S_ISLNK(linked.st_mode), "SETTINGS_DIRECTORY_CHANGED")
        info = n.api.directory(self.fd, n.user.uid, final=True)
        n.api.filesystem(self.fd)
        linked = os.stat(self.name, dir_fd=self.parent, follow_symlinks=False)
        require((info.st_dev, info.st_ino) == self.identity == (linked.st_dev, linked.st_ino)
                and not stat.S_ISLNK(linked.st_mode), "SETTINGS_DIRECTORY_CHANGED")

    def read(self, name):
        require(name in {"settings.json", "settings.pending"}, "SETTINGS_NAME_INVALID")
        self.check()
        try:
            fd = self.native._open_existing(self.fd, name)
        except FileNotFoundError:
            return None
        try:
            before = self.native._regular(fd)
            chunks, remaining = [], MAX_BYTES + 1
            while remaining:
                chunk = os.read(fd, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            after = self.native._regular(fd)
            require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                    == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                    "SETTINGS_CHANGED_RELOAD_REQUIRED")
            raw = b"".join(chunks)
            require(len(raw) <= MAX_BYTES, "SETTINGS_TOO_LARGE")
            return raw
        finally:
            os.close(fd)

    def stage(self, raw):
        require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "SETTINGS_TOO_LARGE")
        self.check()
        fd = os.open("settings.pending", os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)
        try:
            self.native._regular(fd)
            view, offset = memoryview(raw), 0
            while offset < len(raw):
                written = os.write(fd, view[offset:])
                require(written > 0, "SETTINGS_WRITE_FAILED")
                offset += written
            os.fsync(fd)
            self.native._regular(fd)
        finally:
            os.close(fd)

    def promote(self):
        self.check()
        require(self.read("settings.pending") is not None, "SETTINGS_RECOVERY_REQUIRED")
        self.read("settings.json")  # Refuse unsafe existing target before replacement.
        os.replace("settings.pending", "settings.json", src_dir_fd=self.fd, dst_dir_fd=self.fd)
        os.fsync(self.fd)
        self.check()
