"""Bounded fixed-process port, including commissioned OpenSSH forced commands.

Only trusted local commissioning/resolver code supplies argv. Never construct it
from shared data. Host trust, key ownership and purpose belong to that resolver.
No shell, retry, discovery, prompt, alternate root or automatic transport fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
import queue
import subprocess
import threading
import time

from .docs_authority import AuthorityError, require
from .folder_authority import FolderBinding
from .folder_protocol import MAX_WIRE


@dataclass(frozen=True, repr=False)
class FixedProcess:
    binding: FolderBinding
    argv: tuple[str, ...]
    timeout: float = 10.0

    def __post_init__(self):
        require(type(self.binding) is FolderBinding and type(self.argv) is tuple
                and 1 <= len(self.argv) <= 64 and all(type(v) is str and 0 < len(v) <= 4096
                and "\x00" not in v for v in self.argv), "HELPER_COMMAND")
        require(type(self.timeout) in {float, int} and 0 < self.timeout <= 15, "HELPER_TIMEOUT")

    def call(self, raw):
        require(type(raw) is bytes and len(raw) <= MAX_WIRE, "RPC_SIZE")
        child, result = None, queue.Queue(maxsize=1)
        try:
            start = time.monotonic()
            child = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            def write():
                try:
                    child.stdin.write(raw)
                    child.stdin.close()
                except (OSError, ValueError): pass
            def read():
                try: result.put(child.stdout.read(MAX_WIRE + 1))
                except (OSError, ValueError): result.put(None)
            # Daemon readers cannot hold process exit hostage on a broken pipe.
            writer = threading.Thread(target=write, daemon=True)
            reader = threading.Thread(target=read, daemon=True)
            writer.start(); reader.start()
            response = result.get(timeout=max(0.001, self.timeout - (time.monotonic() - start)))
            require(type(response) is bytes and len(response) <= MAX_WIRE, "RPC_SIZE")
            child.wait(timeout=max(0.001, self.timeout - (time.monotonic() - start)))
            require(child.returncode == 0 and time.monotonic() - start <= self.timeout, "HELPER_EXIT")
            return response
        except Exception:
            raise AuthorityError("HELPER_UNAVAILABLE") from None
        finally:
            if child is not None:
                if child.poll() is None: child.kill()
                try: child.wait(timeout=1)
                except subprocess.TimeoutExpired: pass
                # The fixed helper must not detach processes inheriting pipes.
                # Closing after its exit releases the bounded reader/writer.
                for stream in (child.stdin, child.stdout):
                    try: stream.close()
                    except (OSError, ValueError): pass

