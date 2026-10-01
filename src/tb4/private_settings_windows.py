"""Native Windows10+ x64 private R2 settings, explicit ACL only on new objects."""
from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
import hashlib
import ntpath
from pathlib import Path

from .private_settings import MAX_BYTES, SettingsError, require
from .windows_key_native import WindowsKeyNative, FileInfo, local_path


class SecurityAttributes(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", C.c_void_p), ("inherit", W.BOOL)]


class WindowsSettingsNative:
    def __init__(self, root, *, create=False):
        require(isinstance(root, Path) and root.is_absolute(), "SETTINGS_PATH_INVALID")
        self.root = local_path(str(root))
        self.api = WindowsKeyNative()
        self.user = self.api.identity()
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            machine, kind = winreg.QueryValueEx(key, "MachineGuid")
        require(type(machine) is str and 1 <= len(machine) <= 128, "SETTINGS_HOST_UNAVAILABLE")
        self.host = hashlib.sha256(machine.encode("utf-8")).hexdigest()
        def bind(dll, name, result, *args):
            function = getattr(dll, name)
            function.restype, function.argtypes = result, list(args)
        bind(self.api.a, "ConvertStringSecurityDescriptorToSecurityDescriptorW", W.BOOL,
             W.LPCWSTR, W.DWORD, C.POINTER(C.c_void_p), C.POINTER(W.DWORD))
        bind(self.api.k, "CreateDirectoryW", W.BOOL, W.LPCWSTR, C.c_void_p)
        bind(self.api.k, "WriteFile", W.BOOL, C.c_void_p, C.c_void_p, W.DWORD,
             C.POINTER(W.DWORD), C.c_void_p)
        bind(self.api.k, "FlushFileBuffers", W.BOOL, C.c_void_p)
        bind(self.api.k, "MoveFileExW", W.BOOL, W.LPCWSTR, W.LPCWSTR, W.DWORD)
        if create:
            # One new leaf only. Never change an existing directory's owner/ACL.
            parent = self._directory(ntpath.dirname(self.root))
            try:
                with self._security(directory=True) as security:
                    if not self.api.k.CreateDirectoryW(self.root, C.byref(security)):
                        raise SettingsError("SETTINGS_CREATION_UNCONFIRMED")
            finally:
                self.api.k.CloseHandle(parent)

    @contextmanager
    def _security(self, *, directory=False):
        descriptor = C.c_void_p()
        flags = "OICI" if directory else ""
        sddl = ("O:" + self.user.sid + "D:P(A;" + flags + ";FA;;;" + self.user.sid +
                ")(A;" + flags + ";FA;;;SY)(A;" + flags + ";FA;;;BA)")
        require(self.api.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, C.byref(descriptor), None), "SETTINGS_SECURITY_UNAVAILABLE")
        try:
            yield SecurityAttributes(C.sizeof(SecurityAttributes), descriptor, False)
        finally:
            self.api.k.LocalFree(descriptor)

    def _info(self, handle, *, directory=False):
        value = FileInfo()
        require(self.api.k.GetFileType(handle) == 1 and
                self.api.k.GetFileInformationByHandle(handle, C.byref(value)), "SETTINGS_OBJECT")
        require(bool(value.attributes & 0x10) == directory and
                not value.attributes & (0x400 | 0x1000 | 0x40000 | 0x400000), "SETTINGS_OBJECT")
        if not directory:
            require(value.links == 1 and (value.size_high << 32 | value.size_low) <= MAX_BYTES,
                    "SETTINGS_FILE_PROTECTION")
        return value

    def _identity(self, handle):
        value = self._info(handle, directory=True)
        return [value.volume, value.index_high, value.index_low]

    def _location(self, handle, path):
        final = C.create_unicode_buffer(32768)
        size = self.api.k.GetFinalPathNameByHandleW(handle, final, len(final), 0)
        require(0 < size < len(final) and
                ntpath.normcase(final.value.removeprefix("\\\\?\\")) == ntpath.normcase(path),
                "SETTINGS_PATH_CHANGED")
        fs, flags = C.create_unicode_buffer(32), W.DWORD()
        require(self.api.k.GetVolumeInformationByHandleW(handle, None, 0, None, None,
                    C.byref(flags), fs, len(fs)) and fs.value in {"NTFS", "ReFS"}
                and flags.value & 8, "SETTINGS_FILESYSTEM_UNSUPPORTED")

    def _directory(self, path, *, private=True):
        require(self.api.k.GetDriveTypeW(path[:3]) == 3, "SETTINGS_FILESYSTEM_UNSUPPORTED")
        handle = self.api.k.CreateFileW(path, 0x80020000, 3, None, 3, 0x02200000, None)
        require(handle != C.c_void_p(-1).value, "SETTINGS_DIRECTORY_UNAVAILABLE")
        try:
            self._info(handle, directory=True)
            self._location(handle, path)
            if private:
                self.api.permissions(handle, self.user.sid)
            return handle
        except BaseException:
            self.api.k.CloseHandle(handle)
            raise

    def _file(self, name, *, create=False, write=False, exclusive=False):
        require(name in {"settings.lock", "settings.json", "settings.pending"}, "SETTINGS_NAME_INVALID")
        path = ntpath.join(self.root, name)
        with self._security() as security:
            handle = self.api.k.CreateFileW(path, 0xC0020000 if write else 0x80020000,
                0 if exclusive else 1, C.byref(security), 1 if create else 3, 0x00200000, None)
        if handle == C.c_void_p(-1).value:
            error = C.get_last_error()
            if not create and error in {2, 3}:
                return None
            raise SettingsError("SETTINGS_BUSY" if error in {32, 33} else "SETTINGS_FILE_UNAVAILABLE")
        try:
            self._info(handle)
            self._location(handle, path)
            self.api.permissions(handle, self.user.sid)
            return handle
        except BaseException:
            self.api.k.CloseHandle(handle)
            raise

    @contextmanager
    def locked(self):
        root = lock = parent = None
        try:
            require(self.api.identity() == self.user, "SETTINGS_USER_CHANGED")
            parent = self._directory(ntpath.dirname(self.root))
            root = self._directory(self.root)
            # Try opening before exclusive creation; missing-to-create races fail.
            lock = self._file("settings.lock", write=True, exclusive=True)
            if lock is None:
                lock = self._file("settings.lock", create=True, write=True, exclusive=True)
            port = WindowsSettingsPort(self, root, parent)
            port.check()
            yield port
        except SettingsError:
            raise
        except Exception:
            raise SettingsError("SETTINGS_STORE_UNAVAILABLE") from None
        finally:
            if lock is not None:
                self.api.k.CloseHandle(lock)
            if root is not None:
                self.api.k.CloseHandle(root)
            if parent is not None:
                self.api.k.CloseHandle(parent)


class WindowsSettingsPort:
    def __init__(self, native, root, parent):
        self.native, self.root, self.parent = native, root, parent
        self.binding = dict(platform="WINDOWS", host=native.host,
                            principal=native.user.sid, directory=native._identity(root))

    def check(self):
        n = self.native
        require(n.api.identity() == n.user, "SETTINGS_USER_CHANGED")
        n._location(self.parent, ntpath.dirname(n.root))
        n.api.permissions(self.parent, n.user.sid)
        n._location(self.root, n.root)
        n.api.permissions(self.root, n.user.sid)
        require(n._identity(self.root) == self.binding["directory"], "SETTINGS_DIRECTORY_CHANGED")

    def read(self, name):
        require(name in {"settings.json", "settings.pending"}, "SETTINGS_NAME_INVALID")
        self.check()
        handle = self.native._file(name)
        if handle is None:
            return None
        try:
            data, count = C.create_string_buffer(MAX_BYTES + 1), W.DWORD()
            require(self.native.api.k.ReadFile(handle, data, len(data), C.byref(count), None),
                    "SETTINGS_UNREADABLE")
            info = self.native._info(handle)
            require(count.value == (info.size_high << 32 | info.size_low), "SETTINGS_UNREADABLE")
            return data.raw[:count.value]
        finally:
            self.native.api.k.CloseHandle(handle)

    def stage(self, raw):
        require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "SETTINGS_TOO_LARGE")
        self.check()
        handle = self.native._file("settings.pending", create=True, write=True, exclusive=True)
        try:
            data, count = C.create_string_buffer(raw), W.DWORD()
            require(self.native.api.k.WriteFile(handle, data, len(raw), C.byref(count), None)
                    and count.value == len(raw) and self.native.api.k.FlushFileBuffers(handle),
                    "SETTINGS_WRITE_UNCONFIRMED")
            self.native.api.permissions(handle, self.native.user.sid)
        finally:
            self.native.api.k.CloseHandle(handle)

    def promote(self):
        self.check()
        require(self.read("settings.pending") is not None, "SETTINGS_RECOVERY_REQUIRED")
        self.read("settings.json")
        require(self.native.api.k.MoveFileExW(ntpath.join(self.native.root, "settings.pending"),
                    ntpath.join(self.native.root, "settings.json"), 9), "SETTINGS_COMMIT_UNCONFIRMED")
        self.check()
