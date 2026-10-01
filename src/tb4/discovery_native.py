"""Read-only selected-interface discovery. No ping sweep, routing change or shell."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time

from .discovery_catalogue import (DiscoveryError, Interface, Observation, Scope,
                                  address, integer, require)

MAX_OUTPUT = 128 * 1024
MAX_ROWS = 256


class BoundedRead:
    def run(self, argv, *, timeout=5):
        require(type(argv) is tuple and 1 <= len(argv) <= 16
                and all(type(a) is str and 0 < len(a) <= 32768 and "\x00" not in a for a in argv)
                and Path(argv[0]).is_absolute()
                and type(timeout) in {int,float} and 0 < timeout <= 10, "DISCOVERY_COMMAND")
        child = reader = None
        output = queue.Queue(maxsize=1)
        started = time.monotonic()
        try:
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            def read():
                try:
                    output.put(child.stdout.read(MAX_OUTPUT+1))
                except (OSError, ValueError):
                    output.put(None)
            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            raw = output.get(timeout=max(.001,timeout-(time.monotonic()-started)))
            require(type(raw) is bytes and len(raw) <= MAX_OUTPUT, "DISCOVERY_OUTPUT")
            child.wait(timeout=max(.001,timeout-(time.monotonic()-started)))
            require(child.returncode == 0 and time.monotonic()-started <= timeout,
                    "DISCOVERY_UNAVAILABLE")
            return raw
        except Exception:
            raise DiscoveryError("DISCOVERY_UNAVAILABLE") from None
        finally:
            if child is not None:
                if child.poll() is None:
                    child.kill()
                try:
                    child.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    pass
                if reader is not None:
                    reader.join(timeout=.1)
                # A broken provider that leaves an inherited pipe cannot block
                # this caller on a file object's read lock. Reader is bounded/daemon.
                if reader is None or not reader.is_alive():
                    child.stdout.close()


def decoded(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_OUTPUT, "DISCOVERY_OUTPUT")
    def pairs(items):
        result = {}
        for key,value in items:
            require(key not in result, "DISCOVERY_OUTPUT")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8-sig"),object_pairs_hook=pairs,
                           parse_constant=lambda _:require(False,"DISCOVERY_OUTPUT"))
        require(type(value) is list and len(value) <= MAX_ROWS, "DISCOVERY_OUTPUT")
        require(all(type(row) is dict for row in value), "DISCOVERY_OUTPUT")
        return value
    except (ValueError,TypeError,UnicodeError,RecursionError):
        raise DiscoveryError("DISCOVERY_OUTPUT") from None


def system_program(platform):
    if platform == "win32":
        require(sys.platform == "win32", "DISCOVERY_PLATFORM")
        import ctypes as C
        native = C.WinDLL("kernel32",use_last_error=True)
        native.GetSystemDirectoryW.argtypes = [C.c_wchar_p,C.c_uint]
        native.GetSystemDirectoryW.restype = C.c_uint
        buffer = C.create_unicode_buffer(32768)
        size = native.GetSystemDirectoryW(buffer,len(buffer))
        require(0 < size < len(buffer), "DISCOVERY_UNAVAILABLE")
        result = Path(buffer.value)/"WindowsPowerShell"/"v1.0"/"powershell.exe"
    elif platform == "linux":
        require(sys.platform == "linux", "DISCOVERY_PLATFORM")
        result = next((Path(p) for p in ("/usr/sbin/ip","/usr/bin/ip","/sbin/ip","/bin/ip")
                       if Path(p).is_file()),None)
    else:
        raise DiscoveryError("DISCOVERY_PLATFORM")
    require(result is not None and result.is_file(), "DISCOVERY_UNAVAILABLE")
    return str(result)


class NativeNeighbors:
    """The program path/runner are trusted installer ports, never shared JSON."""
    def __init__(self, *, platform=None, program=None, runner=None):
        self.platform = platform or sys.platform
        require(self.platform in {"win32","linux"}, "DISCOVERY_PLATFORM")
        self.program = system_program(self.platform) if program is None else program
        require(type(self.program) is str and Path(self.program).is_absolute(), "DISCOVERY_COMMAND")
        self.runner = runner or BoundedRead()

    def _argv(self, interface, *, neighbors):
        require(type(interface) is Interface, "DISCOVERY_INTERFACE")
        if self.platform == "linux":
            require(re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}",interface.name)
                    and not interface.name.startswith("-"), "DISCOVERY_INTERFACE")
            return (self.program,"-j","neigh" if neighbors else "link","show","dev",interface.name)
        # Only the validated integer index enters this fixed script. The owner
        # name, subnet and device strings are never evaluated as PowerShell.
        command = "Get-NetNeighbor" if neighbors else "Get-NetIPInterface"
        columns = "InterfaceIndex,InterfaceAlias,IPAddress,LinkLayerAddress" if neighbors else "InterfaceIndex,InterfaceAlias"
        script = ("$ErrorActionPreference='Stop';"
                  "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
                  "$tb4Errors=@();$tb4Rows=@("+command+" -InterfaceIndex "+
                  str(interface.index)+" -ErrorAction SilentlyContinue -ErrorVariable tb4Errors"
                  " | Select-Object "+columns+");"
                  "if(@($tb4Errors | Where-Object {$_.CategoryInfo.Category -ne 'ObjectNotFound'}).Count)"
                  "{exit 23};ConvertTo-Json -InputObject $tb4Rows -Compress -Depth 3")
        return (self.program,"-NoLogo","-NoProfile","-NonInteractive","-EncodedCommand",
                base64.b64encode(script.encode("utf-16-le")).decode("ascii"))

    def inspect(self, interface, *, timeout=5):
        rows = decoded(self.runner.run(self._argv(interface,neighbors=False),timeout=timeout))
        if self.platform == "linux":
            require(len(rows)==1 and type(rows[0].get("ifindex")) is int
                    and rows[0].get("ifindex")==interface.index
                    and rows[0].get("ifname")==interface.name, "DISCOVERY_INTERFACE_CHANGED")
        else:
            require(1 <= len(rows) <= 2 and all(
                type(row.get("InterfaceIndex")) is int and row.get("InterfaceIndex")==interface.index
                and row.get("InterfaceAlias")==interface.name
                for row in rows), "DISCOVERY_INTERFACE_CHANGED")

    def read(self, interface, *, timeout=5):
        rows = decoded(self.runner.run(self._argv(interface,neighbors=True),timeout=timeout))
        results = []
        for row in rows:
            if self.platform == "linux":
                require(row.get("dev",interface.name)==interface.name, "DISCOVERY_INTERFACE_CHANGED")
                target,hint = row.get("dst"),row.get("lladdr")
            else:
                require(type(row.get("InterfaceIndex")) is int and row.get("InterfaceIndex")==interface.index
                        and row.get("InterfaceAlias")==interface.name, "DISCOVERY_INTERFACE_CHANGED")
                target,hint = row.get("IPAddress"),row.get("LinkLayerAddress")
            ip = address(target)
            # Broadcast/multicast, unresolved and all-zero cache metadata does
            # not create a device. No provider state is elevated to ONLINE.
            if ip.is_multicast or ip.is_unspecified or str(ip)=="255.255.255.255":
                continue
            require(hint is None or type(hint) is str and len(hint)<=128,
                    "DISCOVERY_OUTPUT")
            if hint is not None:
                hint = hint.strip().lower().replace("-",":") or None
                if hint and not any(c not in "0:" for c in hint):
                    hint = None
            results.append((str(ip),hint))
        return tuple(results)


@dataclass(frozen=True, repr=False)
class Collection:
    observations: tuple[Observation,...]
    status: str
    completed_queries: int
    failed_queries: int

    def summary(self):
        return dict(status=self.status,observed=len(self.observations),
                    completed_queries=self.completed_queries,
                    failed_queries=self.failed_queries)


def collect_neighbors(scope, port, *, clock, monotonic=time.monotonic, timeout=15):
    require(type(scope) is Scope and type(timeout) in {int,float} and 0 < timeout <= 15,
            "DISCOVERY_CONTEXT")
    if not scope.interfaces:
        return Collection((),"ISOLATED",0,0)
    if "NEIGHBOR_CACHE" not in scope.methods:
        return Collection((),"METHOD_UNQUALIFIED",0,len(scope.interfaces))
    deadline = monotonic()+timeout
    found,done,failed = [],0,0
    for interface in scope.interfaces:
        def remaining():
            value = deadline-monotonic()
            require(value>0,"DISCOVERY_UNAVAILABLE")
            return min(5,value)
        try:
            port.inspect(interface,timeout=remaining())
            rows = port.read(interface,timeout=remaining())
            port.inspect(interface,timeout=remaining())
            require(type(rows) is tuple and len(rows)<=MAX_ROWS, "DISCOVERY_OUTPUT")
            now = clock()
            require(integer(now), "DISCOVERY_CLOCK")
            pending=[]
            for target,hint in rows:
                obs=Observation(interface.index,target,"NEIGHBOR_CACHE",now,scope.valid_for_s,
                                hardware_hint=hint)
                if scope.permits(obs):
                    pending.append(obs)
            if len(found)+len(pending)>scope.max_observations:
                return Collection((),"OVERFLOW",done,failed)
            found.extend(pending);done+=1
        except Exception:
            failed+=1
    status="COMPLETE" if not failed else "PARTIAL" if done else "UNAVAILABLE"
    return Collection(tuple(found),status,done,failed)


def collect_fixed(scope, targets, port, *, now, monotonic=time.monotonic, timeout=15):
    """Already qualified bounded fixed-helper port owns route/identity proof.

    This adapter never creates a credential, argv or verified enrollment binding.
    The port must use its commissioned exact interface/endpoint and deadline.
    """
    require(type(scope) is Scope and integer(now) and type(targets) is tuple
            and len(targets)<=scope.max_observations
            and all(type(t) is tuple and len(t)==2 for t in targets)
            and type(timeout) in {int,float} and 0 < timeout <= 15, "DISCOVERY_CONTEXT")
    requests=tuple(Observation(index,target,"FIXED_HELPER",now,scope.valid_for_s)
                   for index,target in targets)
    deadline=monotonic()+timeout
    found,done,failed=[],0,0
    for request in requests:
        if not scope.permits(request):
            failed+=1;continue
        try:
            remaining=deadline-monotonic()
            require(remaining>0,"DISCOVERY_UNAVAILABLE")
            observed=port.observe(request,timeout=min(5,remaining))
            require(type(observed) is Observation and observed.source=="FIXED_HELPER"
                    and (observed.interface_index,observed.address)==
                    (request.interface_index,request.address)
                    and observed.valid_for_s<=scope.valid_for_s
                    and observed.observed_at==now, "DISCOVERY_OUTPUT")
            found.append(observed);done+=1
        except Exception:
            failed+=1
    return Collection(tuple(found),"COMPLETE" if not failed else "PARTIAL" if done else "UNAVAILABLE",
                      done,failed)
