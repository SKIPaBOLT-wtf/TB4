"""Windows 10+ x64 read-only handle/ACL/token adapter. No secret-store mutation."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
import hashlib
import ntpath
import os
import re
import sys

from .credential_contract import Outcome
from .windows_credentials import KeyAccessError, UserSession

MAX_KEY_BYTES = 65536
P = C.c_void_p
DWORD = C.c_uint32
WORD = C.c_uint16
BYTE = C.c_ubyte


class FileInfo(C.Structure):
    _fields_ = [("attributes", DWORD), ("creation", W.FILETIME), ("access", W.FILETIME),
                ("write", W.FILETIME), ("volume", DWORD), ("size_high", DWORD),
                ("size_low", DWORD), ("links", DWORD), ("index_high", DWORD), ("index_low", DWORD)]


class Acl(C.Structure):
    _fields_ = [("revision", BYTE), ("reserved", BYTE), ("size", WORD),
                ("count", WORD), ("reserved2", WORD)]


class SessionInfo(C.Structure):
    _fields_ = [("session", DWORD), ("state", DWORD), ("flags", C.c_int32),
                ("station", W.WCHAR * 33), ("user", W.WCHAR * 21), ("domain", W.WCHAR * 18),
                ("times", C.c_int64 * 5), ("counters", DWORD * 6)]


class ExtendedSessionInfo(C.Structure):
    _fields_ = [("level", DWORD), ("data", SessionInfo)]


def local_path(path):
    if type(path) is not str or not 3 < len(path) <= 1024 or "\x00" in path:
        raise KeyAccessError(Outcome.DENIED)
    normalized = path.replace("/", "\\")
    if not re.fullmatch(r"[A-Za-z]:\\.+", normalized):
        raise KeyAccessError(Outcome.DENIED)
    parts = normalized[3:].split("\\")
    if any(not p or p in {".", ".."} or p[-1] in {" ", "."} or
           any(c in p for c in ':*?"<>|') or
           re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?", p) for p in parts):
        raise KeyAccessError(Outcome.DENIED)
    return normalized


class HeldKey:
    """Internal borrowed native handle, valid only inside open_key's context."""
    __slots__ = ("_api", "_handle", "_sid", "_info", "version")
    def __init__(self, api, handle, sid, info, version):
        self._api, self._handle, self._sid, self._info = api, handle, sid, info
        self.version = version

    @property
    def handle(self):
        if self._handle is None:
            raise KeyAccessError(Outcome.DENIED)
        return self._handle

    def recheck(self):
        self._api.permissions(self.handle, self._sid)
        if self._api.info(self.handle) != self._info:
            raise KeyAccessError(Outcome.REVOKED)

    def process_path(self):
        """Private fixed-helper input while this no-write/delete handle is held."""
        self.recheck()
        value = C.create_unicode_buffer(32768)
        size = self._api.k.GetFinalPathNameByHandleW(self.handle, value, len(value), 0)
        if not 0 < size < len(value):
            raise KeyAccessError(Outcome.DENIED)
        path = local_path(value.value.removeprefix("\\\\?\\"))
        self.recheck()
        return path


class WindowsKeyNative:
    def __init__(self):
        if os.name != "nt" or C.sizeof(P) != 8 or sys.getwindowsversion().major < 10:
            raise KeyAccessError()
        self.k = C.WinDLL("kernel32", use_last_error=True)
        self.a = C.WinDLL("advapi32", use_last_error=True)
        self.w = C.WinDLL("wtsapi32", use_last_error=True)
        def bind(dll, name, result, *args):
            fn = getattr(dll, name)
            fn.restype, fn.argtypes = result, list(args)
        bind(self.k, "GetCurrentProcess", P)
        bind(self.k, "GetCurrentThread", P)
        bind(self.k, "CloseHandle", W.BOOL, P)
        bind(self.k, "LocalFree", P, P)
        bind(self.a, "OpenProcessToken", W.BOOL, P, DWORD, C.POINTER(P))
        bind(self.a, "OpenThreadToken", W.BOOL, P, DWORD, W.BOOL, C.POINTER(P))
        bind(self.a, "GetTokenInformation", W.BOOL, P, DWORD, P, DWORD, C.POINTER(DWORD))
        bind(self.a, "ConvertSidToStringSidW", W.BOOL, P, C.POINTER(P))
        bind(self.a, "IsValidSid", W.BOOL, P)
        bind(self.a, "GetLengthSid", DWORD, P)
        bind(self.a, "GetSecurityInfo", DWORD, P, DWORD, DWORD, C.POINTER(P),
             C.POINTER(P), C.POINTER(P), C.POINTER(P), C.POINTER(P))
        bind(self.a, "IsValidAcl", W.BOOL, P)
        bind(self.a, "GetAce", W.BOOL, P, DWORD, C.POINTER(P))
        bind(self.k, "CreateFileW", P, W.LPCWSTR, DWORD, DWORD, P, DWORD, DWORD, P)
        bind(self.k, "GetFileType", DWORD, P)
        bind(self.k, "GetFileInformationByHandle", W.BOOL, P, C.POINTER(FileInfo))
        bind(self.k, "GetFinalPathNameByHandleW", DWORD, P, W.LPWSTR, DWORD, DWORD)
        bind(self.k, "GetVolumeInformationByHandleW", W.BOOL, P, W.LPWSTR, DWORD,
             C.POINTER(DWORD), C.POINTER(DWORD), C.POINTER(DWORD), W.LPWSTR, DWORD)
        bind(self.k, "GetDriveTypeW", DWORD, W.LPCWSTR)
        bind(self.k, "ReadFile", W.BOOL, P, P, DWORD, C.POINTER(DWORD), P)
        bind(self.k, "SetFilePointerEx", W.BOOL, P, C.c_int64, P, DWORD)
        bind(self.w, "WTSQuerySessionInformationW", W.BOOL, P, DWORD, DWORD,
             C.POINTER(P), C.POINTER(DWORD))
        bind(self.w, "WTSFreeMemory", None, P)

    def _failed(self):
        code = C.get_last_error()
        raise KeyAccessError({2: Outcome.ABSENT, 3: Outcome.ABSENT, 5: Outcome.DENIED,
                              32: Outcome.LOCKED, 33: Outcome.LOCKED}.get(code, Outcome.STORE_UNAVAILABLE))

    def _sid(self, pointer):
        if not pointer or not self.a.IsValidSid(pointer):
            raise KeyAccessError(Outcome.DENIED)
        text = P()
        if not self.a.ConvertSidToStringSidW(pointer, C.byref(text)):
            self._failed()
        try:
            return C.wstring_at(text)
        finally:
            self.k.LocalFree(text)

    def _token_info(self, token, kind):
        size = DWORD()
        self.a.GetTokenInformation(token, kind, None, 0, C.byref(size))
        if not 0 < size.value <= 65536:
            raise KeyAccessError()
        data = C.create_string_buffer(size.value)
        if not self.a.GetTokenInformation(token, kind, data, size, C.byref(size)):
            self._failed()
        return data

    def identity(self):
        token = P()
        # A thread impersonation token must never silently use process identity.
        if self.a.OpenThreadToken(self.k.GetCurrentThread(), 8, True, C.byref(token)):
            self.k.CloseHandle(token)
            raise KeyAccessError(Outcome.DENIED)
        if C.get_last_error() != 1008:  # ERROR_NO_TOKEN
            self._failed()
        if not self.a.OpenProcessToken(self.k.GetCurrentProcess(), 8, C.byref(token)):
            self._failed()
        try:
            user = self._token_info(token, 1)
            sid = self._sid(P.from_buffer(user).value)
            session = DWORD.from_buffer(self._token_info(token, 12)).value
            stats = self._token_info(token, 10)
            if len(stats) < 16:
                raise KeyAccessError()
            logon = (DWORD.from_buffer(stats, 8).value, DWORD.from_buffer(stats, 12).value)
            return UserSession(sid, session, logon)
        finally:
            self.k.CloseHandle(token)

    def interactive(self, session):
        value, size = P(), DWORD()
        if not self.w.WTSQuerySessionInformationW(None, session, 25, C.byref(value), C.byref(size)):
            raise KeyAccessError()
        try:
            if size.value < C.sizeof(ExtendedSessionInfo):
                raise KeyAccessError()
            result = C.cast(value, C.POINTER(ExtendedSessionInfo)).contents
            return (result.level == 1 and result.data.session == session and
                    result.data.state == 0 and result.data.flags == 1)
        finally:
            self.w.WTSFreeMemory(value)

    def permissions(self, handle, sid):
        owner, dacl, descriptor = P(), P(), P()
        code = self.a.GetSecurityInfo(handle, 1, 5, C.byref(owner), None,
                                     C.byref(dacl), None, C.byref(descriptor))
        if code:
            raise KeyAccessError(Outcome.DENIED)
        try:
            if self._sid(owner) != sid or not dacl or not self.a.IsValidAcl(dacl):
                raise KeyAccessError(Outcome.DENIED)
            acl = C.cast(dacl, C.POINTER(Acl)).contents
            if not 0 < acl.count <= 1024 or not 8 <= acl.size <= 65535:
                raise KeyAccessError(Outcome.DENIED)
            allowed = {sid, "S-1-5-18", "S-1-5-32-544"}  # owner, SYSTEM, local administrators
            for i in range(acl.count):
                ace = P()
                if not self.a.GetAce(dacl, i, C.byref(ace)):
                    raise KeyAccessError(Outcome.DENIED)
                start = ace.value
                kind, flags = BYTE.from_address(start).value, BYTE.from_address(start + 1).value
                size = WORD.from_address(start + 2).value
                if kind not in {0, 1} or size < 16 or start < dacl.value + 8 or start + size > dacl.value + acl.size:
                    raise KeyAccessError(Outcome.DENIED)
                trustee = start + 8
                if not self.a.IsValidSid(trustee) or self.a.GetLengthSid(trustee) > size - 8:
                    raise KeyAccessError(Outcome.DENIED)
                mask = DWORD.from_address(start + 4).value
                if kind == 0 and not flags & 8 and mask and self._sid(trustee) not in allowed:
                    raise KeyAccessError(Outcome.DENIED)
        finally:
            self.k.LocalFree(descriptor)

    def info(self, handle):
        info = FileInfo()
        if self.k.GetFileType(handle) != 1 or not self.k.GetFileInformationByHandle(handle, C.byref(info)):
            raise KeyAccessError(Outcome.DENIED)
        # Directories, reparse points and offline/cloud placeholders are unsupported.
        if info.attributes & (0x10 | 0x400 | 0x1000 | 0x40000 | 0x400000) or info.links != 1:
            raise KeyAccessError(Outcome.DENIED)
        size = (info.size_high << 32) | info.size_low
        if not 0 < size <= MAX_KEY_BYTES:
            raise KeyAccessError(Outcome.DENIED)
        return (info.volume, info.index_high, info.index_low, size,
                info.write.dwHighDateTime, info.write.dwLowDateTime)

    def _version(self, handle, info):
        data = C.create_string_buffer(MAX_KEY_BYTES + 1)
        count = DWORD()
        try:
            if not self.k.ReadFile(handle, data, len(data), C.byref(count), None):
                self._failed()
            if count.value != info[3] or self.info(handle) != info:
                raise KeyAccessError(Outcome.REVOKED)
            digest = hashlib.sha256(repr(info).encode("ascii"))
            digest.update(memoryview(data)[:count.value])
            return int.from_bytes(digest.digest(), "big") + 1
        finally:
            C.memset(C.addressof(data), 0, len(data))
            if not self.k.SetFilePointerEx(handle, 0, None, 0):
                self._failed()

    @contextmanager
    def open_key(self, path, sid):
        path = local_path(path)
        if self.k.GetDriveTypeW(path[:3]) != 3:
            raise KeyAccessError(Outcome.DENIED)
        # OPEN_EXISTING, READ_CONTROL|GENERIC_READ, FILE_SHARE_READ only:
        # no creation, no writer/delete sharing, no inherited handle.
        handle = self.k.CreateFileW(path, 0x80020000, 1, None, 3, 0x00200000, None)
        if handle == P(-1).value:
            self._failed()
        key = None
        try:
            final = C.create_unicode_buffer(32768)
            size = self.k.GetFinalPathNameByHandleW(handle, final, len(final), 0)
            if not 0 < size < len(final) or ntpath.normcase(final.value.removeprefix("\\\\?\\")) != ntpath.normcase(path):
                raise KeyAccessError(Outcome.DENIED)
            fs, flags = C.create_unicode_buffer(32), DWORD()
            if not self.k.GetVolumeInformationByHandleW(handle, None, 0, None, None,
                                                       C.byref(flags), fs, len(fs)):
                self._failed()
            if fs.value not in {"NTFS", "ReFS"} or not flags.value & 8:
                raise KeyAccessError(Outcome.DENIED)
            self.permissions(handle, sid)
            info = self.info(handle)
            key = HeldKey(self, handle, sid, info, self._version(handle, info))
            key.recheck()
            yield key
        finally:
            if key is not None:
                key._handle = None
            self.k.CloseHandle(handle)
